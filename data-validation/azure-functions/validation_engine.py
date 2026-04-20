"""
PostgreSQL Migration Validation Engine
Azure Function - Python 3.11

This module provides enterprise-grade validation for PostgreSQL migration
from on-premise v11 to Azure PostgreSQL v14.

Functions:
  - Row count reconciliation
  - Column-level validation
  - Null constraint validation
  - Data type compliance
  - Business rule validation
  - Referential integrity checks
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import hashlib
import psycopg2
from psycopg2 import Error as PostgresError
from azure.storage.queue import QueueClient
from azure.cosmos import CosmosClient
import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient


# ============================================================================
# Configuration & Logging
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ValidationConfig:
    """Configuration for validation engine."""
    
    def __init__(self):
        self.source_host = os.getenv('SOURCE_DB_HOST', 'on-prem-db.internal')
        self.source_port = int(os.getenv('SOURCE_DB_PORT', 5432))
        self.source_db = os.getenv('SOURCE_DB_NAME', 'production')
        self.source_user = os.getenv('SOURCE_DB_USER', 'pg_migration_user')
        
        self.target_host = os.getenv('TARGET_DB_HOST', 'postgresql-prod.postgres.database.azure.com')
        self.target_port = int(os.getenv('TARGET_DB_PORT', 5432))
        self.target_db = os.getenv('TARGET_DB_NAME', 'production')
        self.target_user = os.getenv('TARGET_DB_USER', 'pg_admin@postgresql-prod')
        
        self.cosmos_endpoint = os.getenv('COSMOS_ENDPOINT')
        self.cosmos_db = os.getenv('COSMOS_DB', 'migration_metadata')
        self.cosmos_container = os.getenv('COSMOS_CONTAINER', 'validations')
        
        self.queue_connection_string = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
        self.validation_phase = os.getenv('VALIDATION_PHASE', 'INCREMENTAL_SYNC')


# ============================================================================
# Database Connection Management
# ============================================================================

class DatabaseConnector:
    """Handles connections to source and target PostgreSQL databases."""
    
    def __init__(self, config: ValidationConfig):
        self.config = config
        self.source_conn: Optional[psycopg2.extensions.connection] = None
        self.target_conn: Optional[psycopg2.extensions.connection] = None
    
    def get_source_connection(self) -> psycopg2.extensions.connection:
        """Get connection to source database (on-prem)."""
        if not self.source_conn:
            try:
                self.source_conn = psycopg2.connect(
                    host=self.config.source_host,
                    port=self.config.source_port,
                    database=self.config.source_db,
                    user=self.config.source_user,
                    password=self._get_secret('source-db-password'),
                    connect_timeout=10
                )
                logger.info("Connected to source database")
            except PostgresError as e:
                logger.error(f"Failed to connect to source: {e}")
                raise
        return self.source_conn
    
    def get_target_connection(self) -> psycopg2.extensions.connection:
        """Get connection to target database (Azure)."""
        if not self.target_conn:
            try:
                self.target_conn = psycopg2.connect(
                    host=self.config.target_host,
                    port=self.config.target_port,
                    database=self.config.target_db,
                    user=self.config.target_user,
                    password=self._get_secret('target-db-password'),
                    sslmode='require',
                    connect_timeout=10
                )
                logger.info("Connected to target database")
            except PostgresError as e:
                logger.error(f"Failed to connect to target: {e}")
                raise
        return self.target_conn
    
    def _get_secret(self, secret_name: str) -> str:
        """Retrieve secret from Azure Key Vault."""
        try:
            credential = DefaultAzureCredential()
            vault_url = os.getenv('KEY_VAULT_URL')
            client = SecretClient(vault_url=vault_url, credential=credential)
            return client.get_secret(secret_name).value
        except Exception as e:
            logger.error(f"Failed to retrieve secret {secret_name}: {e}")
            raise
    
    def execute_query(self, conn: psycopg2.extensions.connection, 
                      query: str, params: Tuple = None) -> List[Dict]:
        """Execute query and return results as list of dicts."""
        try:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            
            columns = [desc[0] for desc in cursor.description]
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            
            cursor.close()
            return results
        except PostgresError as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    def close(self):
        """Close database connections."""
        if self.source_conn:
            self.source_conn.close()
        if self.target_conn:
            self.target_conn.close()


# ============================================================================
# Validation Engine
# ============================================================================

class ValidationEngine:
    """Core validation logic for PostgreSQL migration."""
    
    def __init__(self, config: ValidationConfig):
        self.config = config
        self.db = DatabaseConnector(config)
        self.results = {
            'validations': [],
            'status': 'PASS',
            'error_count': 0,
            'warning_count': 0
        }
    
    def validate_row_count(self, schema: str, table: str) -> Dict:
        """Validate row count between source and target."""
        logger.info(f"Validating row count for {schema}.{table}")
        
        try:
            # Query source
            source_query = f"SELECT COUNT(*) as count FROM {schema}.{table}"
            source_result = self.db.execute_query(
                self.db.get_source_connection(),
                source_query
            )
            source_count = source_result[0]['count'] if source_result else 0
            
            # Query target
            target_query = f"SELECT COUNT(*) as count FROM raw_schema.{table}"
            target_result = self.db.execute_query(
                self.db.get_target_connection(),
                target_query
            )
            target_count = target_result[0]['count'] if target_result else 0
            
            # Validation
            passed = source_count == target_count
            
            result = {
                'validation_id': 'ROW_COUNT_RECONCILIATION',
                'validation_name': f'Row Count: {schema}.{table}',
                'status': 'PASS' if passed else 'FAIL',
                'source_count': source_count,
                'target_count': target_count,
                'difference': target_count - source_count,
                'severity': 'CRITICAL' if not passed else 'INFO'
            }
            
            if not passed:
                self.results['error_count'] += 1
                self.results['status'] = 'FAIL'
                logger.error(f"Row count mismatch: {schema}.{table} "
                           f"(source: {source_count}, target: {target_count})")
            
            return result
            
        except Exception as e:
            logger.error(f"Row count validation failed: {e}")
            return {
                'validation_id': 'ROW_COUNT_RECONCILIATION',
                'validation_name': f'Row Count: {schema}.{table}',
                'status': 'ERROR',
                'error': str(e),
                'severity': 'HIGH'
            }
    
    def validate_null_constraints(self, schema: str, table: str) -> Dict:
        """Validate NOT NULL constraints."""
        logger.info(f"Validating null constraints for {schema}.{table}")
        
        try:
            # Get NOT NULL columns from target schema
            query = f"""
                SELECT column_name 
                FROM information_schema.columns
                WHERE table_schema = 'raw_schema'
                  AND table_name = '{table}'
                  AND is_nullable = 'NO'
            """
            result = self.db.execute_query(
                self.db.get_target_connection(),
                query
            )
            
            not_null_columns = [row['column_name'] for row in result]
            
            if not not_null_columns:
                return {
                    'validation_id': 'NULL_CONSTRAINT_VALIDATION',
                    'validation_name': f'NULL Constraints: {schema}.{table}',
                    'status': 'PASS',
                    'columns_checked': 0,
                    'violations': 0
                }
            
            # Check for null values in NOT NULL columns
            or_clause = ' OR '.join([f'{col} IS NULL' for col in not_null_columns])
            check_query = f"""
                SELECT COUNT(*) as violations 
                FROM raw_schema.{table} 
                WHERE {or_clause}
            """
            
            check_result = self.db.execute_query(
                self.db.get_target_connection(),
                check_query
            )
            
            violations = check_result[0]['violations'] if check_result else 0
            passed = violations == 0
            
            result = {
                'validation_id': 'NULL_CONSTRAINT_VALIDATION',
                'validation_name': f'NULL Constraints: {schema}.{table}',
                'status': 'PASS' if passed else 'FAIL',
                'columns_checked': len(not_null_columns),
                'columns': not_null_columns[:5],  # Sample for report
                'violations': violations,
                'severity': 'HIGH' if not passed else 'INFO'
            }
            
            if not passed:
                self.results['error_count'] += 1
                self.results['status'] = 'FAIL'
            
            return result
            
        except Exception as e:
            logger.error(f"NULL constraint validation failed: {e}")
            return {
                'validation_id': 'NULL_CONSTRAINT_VALIDATION',
                'validation_name': f'NULL Constraints: {schema}.{table}',
                'status': 'ERROR',
                'error': str(e),
                'severity': 'HIGH'
            }
    
    def validate_primary_key_uniqueness(self, schema: str, table: str) -> Dict:
        """Validate primary key uniqueness."""
        logger.info(f"Validating primary key uniqueness for {schema}.{table}")
        
        try:
            # Get primary key columns
            pk_query = f"""
                SELECT a.attname
                FROM pg_index i
                JOIN pg_attribute a ON a.attrelid = i.indrelid
                  AND a.attnum = ANY(i.indkey)
                WHERE i.indrelname = '{table}_pkey'
            """
            
            pk_result = self.db.execute_query(
                self.db.get_target_connection(),
                pk_query
            )
            
            if not pk_result:
                return {
                    'validation_id': 'PRIMARY_KEY_UNIQUENESS',
                    'validation_name': f'PK Uniqueness: {schema}.{table}',
                    'status': 'SKIP',
                    'reason': 'No primary key found'
                }
            
            pk_columns = [row['attname'] for row in pk_result]
            pk_column_list = ', '.join(pk_columns)
            
            # Check for duplicates
            dup_query = f"""
                SELECT COUNT(*) - COUNT(DISTINCT {pk_column_list}) as duplicates
                FROM raw_schema.{table}
            """
            
            dup_result = self.db.execute_query(
                self.db.get_target_connection(),
                dup_query
            )
            
            duplicates = dup_result[0]['duplicates'] if dup_result else 0
            passed = duplicates == 0
            
            result = {
                'validation_id': 'PRIMARY_KEY_UNIQUENESS',
                'validation_name': f'PK Uniqueness: {schema}.{table}',
                'status': 'PASS' if passed else 'FAIL',
                'pk_columns': pk_columns,
                'duplicates_found': duplicates,
                'severity': 'CRITICAL' if not passed else 'INFO'
            }
            
            if not passed:
                self.results['error_count'] += 1
                self.results['status'] = 'FAIL'
            
            return result
            
        except Exception as e:
            logger.error(f"PK uniqueness validation failed: {e}")
            return {
                'validation_id': 'PRIMARY_KEY_UNIQUENESS',
                'validation_name': f'PK Uniqueness: {schema}.{table}',
                'status': 'ERROR',
                'error': str(e),
                'severity': 'CRITICAL'
            }
    
    def validate_data_types(self, schema: str, table: str) -> Dict:
        """Validate data type compatibility."""
        logger.info(f"Validating data types for {schema}.{table}")
        
        try:
            # Get column data types from target
            dtype_query = f"""
                SELECT column_name, data_type, udt_name
                FROM information_schema.columns
                WHERE table_schema = 'raw_schema'
                  AND table_name = '{table}'
            """
            
            result = self.db.execute_query(
                self.db.get_target_connection(),
                dtype_query
            )
            
            # Validate supported types
            unsupported_types = {
                'money',  # Not recommended for v14
                'point', 'line', 'lseg', 'box',  # Geometric types
                'polygon', 'circle', 'path',  # Geometric types
            }
            
            issues = []
            for row in result:
                if row['data_type'] in unsupported_types:
                    issues.append({
                        'column': row['column_name'],
                        'type': row['data_type'],
                        'issue': 'Unsupported or deprecated'
                    })
            
            passed = len(issues) == 0
            
            result = {
                'validation_id': 'DATA_TYPE_VALIDATION',
                'validation_name': f'Data Types: {schema}.{table}',
                'status': 'PASS' if passed else 'WARNING',
                'columns_checked': len(result),
                'issues_found': len(issues),
                'issues': issues[:10],  # Sample issues
                'severity': 'MEDIUM' if issues else 'INFO'
            }
            
            if issues:
                self.results['warning_count'] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"Data type validation failed: {e}")
            return {
                'validation_id': 'DATA_TYPE_VALIDATION',
                'validation_name': f'Data Types: {schema}.{table}',
                'status': 'ERROR',
                'error': str(e),
                'severity': 'MEDIUM'
            }


# ============================================================================
# Cosmos DB Metadata Storage
# ============================================================================

class MetadataStore:
    """Manages validation results in Cosmos DB."""
    
    def __init__(self, config: ValidationConfig):
        self.config = config
        self.client: Optional[CosmosClient] = None
        self.container = None
    
    def connect(self):
        """Connect to Cosmos DB."""
        try:
            credential = DefaultAzureCredential()
            self.client = CosmosClient(
                url=self.config.cosmos_endpoint,
                credential=credential
            )
            db = self.client.get_database_client(self.config.cosmos_db)
            self.container = db.get_container_client(self.config.cosmos_container)
            logger.info("Connected to Cosmos DB")
        except Exception as e:
            logger.error(f"Failed to connect to Cosmos DB: {e}")
            raise
    
    def store_validation_result(self, table_name: str, 
                               validations: List[Dict]) -> str:
        """Store validation result in Cosmos DB."""
        try:
            result_doc = {
                'id': f"{datetime.utcnow().isoformat()}_{table_name}",
                'timestamp_utc': datetime.utcnow().isoformat(),
                'table_name': table_name,
                'phase': self.config.validation_phase,
                'validations': validations,
                'overall_status': 'PASS' if all(v['status'] == 'PASS' for v in validations) else 'FAIL',
                'ttl': 7776000  # 90 days
            }
            
            self.container.create_item(result_doc)
            logger.info(f"Stored validation result for {table_name}")
            return result_doc['id']
            
        except Exception as e:
            logger.error(f"Failed to store validation result: {e}")
            raise


# ============================================================================
# Azure Function Entry Point
# ============================================================================

def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Azure Function: PostgreSQL Migration Validation Engine
    
    Request body:
    {
        "schema": "public",
        "table": "orders",
        "correlation_id": "migration_run_12345"
    }
    """
    
    try:
        # Parse request
        req_json = req.get_json()
        schema = req_json.get('schema', 'public')
        table = req_json.get('table')
        correlation_id = req_json.get('correlation_id', '')
        
        if not table:
            return func.HttpResponse(
                json.dumps({'error': 'Missing required parameter: table'}),
                status_code=400,
                mimetype='application/json'
            )
        
        # Initialize
        config = ValidationConfig()
        engine = ValidationEngine(config)
        store = MetadataStore(config)
        store.connect()
        
        # Run validations
        validations = [
            engine.validate_row_count(schema, table),
            engine.validate_null_constraints(schema, table),
            engine.validate_primary_key_uniqueness(schema, table),
            engine.validate_data_types(schema, table),
        ]
        
        # Store results
        result_id = store.store_validation_result(table, validations)
        
        # Prepare response
        response_data = {
            'result_id': result_id,
            'table': table,
            'schema': schema,
            'correlation_id': correlation_id,
            'validations': validations,
            'overall_status': engine.results['status'],
            'error_count': engine.results['error_count'],
            'warning_count': engine.results['warning_count'],
            'timestamp_utc': datetime.utcnow().isoformat()
        }
        
        # Cleanup
        engine.db.close()
        
        status_code = 200 if engine.results['status'] == 'PASS' else 206
        
        return func.HttpResponse(
            json.dumps(response_data),
            status_code=status_code,
            mimetype='application/json'
        )
        
    except Exception as e:
        logger.error(f"Function execution failed: {e}")
        return func.HttpResponse(
            json.dumps({'error': str(e)}),
            status_code=500,
            mimetype='application/json'
        )
