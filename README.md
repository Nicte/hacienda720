# Modelo 720 – Mintos

Utilidades para generar el archivo de importación del Modelo 720 (declaración de bienes y derechos en el extranjero) a partir de los exports de la plataforma Mintos.

**Aviso legal.** Esta herramienta no es oficial ni está respaldada por la AEAT, Mintos ni ninguna administración. Se ofrece “tal cual”, sin garantías. El usuario es responsable de verificar los datos y de la correcta presentación del Modelo 720. Consulta con un asesor fiscal si tienes dudas.

## Requisitos

- Python 3.8+
- Dependencias: `pip install -r requirements.txt`

## Uso

### 1. Configuración

Copia el archivo de ejemplo y rellena tus datos:

```bash
cp .env.example .env
```

Abre `.env` y edita los valores:

```ini
# Datos personales (obligatorios)
NAME=APELLIDO1 APELLIDO2 NOMBRE
DNI=12345678X
PHONE=600000000

# Años a declarar
CURRENT_YEAR=2025
PREVIOUS_YEAR=2024
```

El archivo `.env` está en `.gitignore` y nunca se sube al repositorio. Los valores opcionales (`INPUT_DIR`, `OUTPUT_DIR`, etc.) tienen valores por defecto y solo necesitas incluirlos si quieres cambiarlos.

### 2. Archivos de entrada

- La carpeta `input/` está en el repositorio; los archivos que pongas dentro **no** se suben a git (están en `.gitignore`) para no comprometer datos personales.
- Coloca ahí **todos** los exports de Mintos del año a declarar y del año anterior:
  - **Año actual**: archivos cuyo nombre contenga el año a declarar (p. ej. `Mintos 2025 Loans.xlsx`, `Bonds 2025.xlsx`).
  - **Año anterior** (opcional): archivos con el año anterior (p. ej. `Mintos 2024 ...`) para marcar altas/bajas/modificaciones.
- El script acepta **Excel** (`.xlsx`, `.xls`) y **CSV**.
- Los nombres de columnas se comparan **sin distinguir mayúsculas/minúsculas**.
- Puede haber columnas extra, pero estas son obligatorias:

#### Formato esperado: Loans

- `Issuer name`
- `ISIN`
- `Issuer Registration number`
- `Outstanding investments LOC`

#### Formato esperado: Bonds

- `Issuer name`
- `ISIN`
- `Issuer Registration number`
- `Amount`
- `Type`

Para **bonds**, solo se tienen en cuenta filas con `Type = Investment` (ignorando mayúsculas/minúsculas). El importe que se usa es `abs(Amount)` para evitar que el signo del export distorsione el total declarado.

- Si falta alguna columna obligatoria, el script se detiene y muestra un error con el detalle por archivo.
- Si exportas CSV: mantén todos los decimales (suelen ser 6) y un formato de número válido (español (12.345,67), ingles (12,345.67) o estandar (12345.67)). En `mintos.py` puedes cambiar `CSV_DELIMITER` a `","` o `";"` según tu exportación.

### 3. Generar el archivo .720

```bash
python mintos.py
```

Se creará la carpeta de salida si no existe y el archivo se escribirá en `OUTPUT_DIR/modelo_720_<CURRENT_YEAR>.720` (o en `OUTPUT_DIR/OUTPUT_FILENAME` si defines `OUTPUT_FILENAME`).

### 4. Validar

Comprueba que el total y el número de registros coinciden con los datos de entrada:

```bash
python validate_720.py
```

Si algo no cuadra, el script indicará las diferencias.

### 5. Subir a Hacienda

Importa el archivo `.720` en la herramienta web de la AEAT para presentar el Modelo 720.

## Notas

- Los activos con saldo 0 no se incluyen.
- En bonds se agregan únicamente las filas de tipo `Investment`, agrupadas por ISIN. Las filas que no son `Investment` (intereses, pagos, etc.) se ignoran para el cálculo.
