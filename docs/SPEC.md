# Ledger Pipeline

## Descripción
Reconstrucción, con datos sintéticos, del pipeline financiero que conecta un ERP (tipo SAP) con un sistema de consolidación (tipo Oracle FCCS/HFM). Muestra el patrón staging + auditoría y reproduce la mejora de rendimiento de producción (15 min a 42 s).

## Objetivos
- Generador de asientos contables sintéticos (170.000+ filas, cuentas, entidades, periodos).
- Carga a SQL Server en tablas `stg.*` con validaciones de calidad.
- Esquema `ctl.*` de auditoría: RunID, inicio/fin, filas leídas/cargadas/rechazadas, errores.
- Benchmark reproducible: carga fila por fila vs carga masiva (bulk insert / fast_executemany).
- Exportación en el formato de archivo que espera el sistema de consolidación.

## Stack Tecnológico
- **Lenguaje**: Python 3 (pandas, pyodbc / SQLAlchemy).
- **Base de Datos**: SQL Server Express en Docker.
- **Calidad**: pytest, GitHub Actions con un contenedor de SQL Server.

## Requerimientos y Casos de Uso Buscados
- Patrones de carga masiva en SQL Server desde Python.
- Diseño de esquemas de staging y control para ETL auditable.
- Generación de datos sintéticos realistas (Faker o generador propio).
- Nada de datos ni código de clientes: todo sintético.
