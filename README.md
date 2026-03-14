# Modelo 720 – Mintos

Utilidades para generar el archivo de importación del Modelo 720 (declaración de bienes y derechos en el extranjero) a partir de los exports de la plataforma Mintos.

**Aviso legal.** Esta herramienta no es oficial ni está respaldada por la AEAT, Mintos ni ninguna administración. Se ofrece “tal cual”, sin garantías. El usuario es responsable de verificar los datos y de la correcta presentación del Modelo 720. Consulta con un asesor fiscal si tienes dudas.

## Requisitos

- Python 3.8+
- Dependencias: `pip install -r requirements.txt`

## Uso

### 1. Configuración

Edita la sección de configuración al inicio de `mintos.py`:

- **INPUT_DIR**: carpeta donde pondrás los archivos de Mintos (Excel o CSV).
- **OUTPUT_DIR**: carpeta donde se generará el archivo `.720`.
- **CURRENT_YEAR** / **PREVIOUS_YEAR**: año a declarar y año anterior (para detectar qué archivos son de cada ejercicio).
- **OUTPUT_FILENAME**: nombre del archivo generado (p. ej. `modelo_720.720`).
- **NAME**, **DNI**, **PHONE**: tus datos para el formulario.

### 2. Archivos de entrada

- La carpeta `input/` está en el repositorio; los archivos que pongas dentro **no** se suben a git (están en `.gitignore`) para no comprometer datos personales.
- Coloca ahí **todos** los exports de Mintos del año a declarar y del año anterior:
  - **Año actual**: archivos cuyo nombre contenga el año a declarar (p. ej. `Mintos 2025 Loans.xlsx`, `Bonds 2025.xlsx`).
  - **Año anterior** (opcional): archivos con el año anterior (p. ej. `Mintos 2024 ...`) para marcar altas/bajas/modificaciones.
- El script acepta **Excel** (`.xlsx`, `.xls`) y **CSV**. Detecta solo si es “loans” (columna *Outstanding investments LOC*) o “bonds” (columna *Amount* + *ISIN*).
- Si exportas CSV: mantén todos los decimales (suelen ser 6) y un formato de número válido (español (12.345,67), ingles (12,345.67) o estandar (12345.67)). En `mintos.py` puedes cambiar `CSV_DELIMITER` a `","` o `";"` según tu exportación.

### 3. Generar el archivo .720

```bash
python mintos.py
```

Se creará la carpeta de salida si no existe y el archivo se escribirá en `OUTPUT_DIR/OUTPUT_FILENAME`.

### 4. Validar

Comprueba que el total y el número de registros coinciden con los datos de entrada:

```bash
python validate_720.py
```

Si algo no cuadra, el script indicará las diferencias.

### 5. Subir a Hacienda

Importa el archivo `.720` en la herramienta web de la AEAT para presentar el Modelo 720.

## Notas

- **Bonds**: el export de bonds de Mintos no trae *Issuer name* ni *Issuer registration number*. En `mintos.py` está el diccionario `BOND_ISIN_TO_ISSUER` para indicar esos datos por ISIN (añade los que uses y, si hace falta, el número de registro).
- Los activos con saldo 0 no se incluyen. Los bonds se agregan por ISIN sumando la columna *Amount* (solo se declaran con saldo total &gt; 0).
