# Grimmory Book Manager

Grimmory Book Manager es una aplicación web para gestionar una biblioteca de libros electrónicos (ebooks). Permite buscar libros en indexadores de Jackett, descargarlos con qBittorrent y mantener sincronizada la biblioteca con Grimmory.

## Funcionalidades

- **Búsqueda de libros**: Busca ebooks en Jackett (epublibre y otros indexadores) por título, autor o ISBN.
- **Gestión de descargas**: Añade torrents directamente desde la interfaz, con gestión de estado (descargando, pausado, seedando).
- **Biblioteca local**: Consulta y gestiona la biblioteca de Grimmory.
- **Sincronización automática**: Sincroniza periódicamente el estado de las descargas con Grimmory, actualizando rutas de archivos automáticamente.
- **Panel de control**: Dashboard con estadísticas de descargas y estado de servicios.

## Servicios necesarios

| Servicio | Propósito |
|---|---|
| [Grimmory](https://github.com/grimmory/grimmory) | Gestión de la biblioteca de libros |
| [qBittorrent](https://www.qbittorrent.org/) | Cliente de descarga de torrents |
| [Jackett](https://github.com/Jackett/Jackett) | Proxy de indexadores para buscar torrents |

## Instalación con Docker

### 1. Clonar el repositorio

```bash
git clone https://github.com/Jesuslconde/grimmory-book-manager.git
cd grimmory-book-manager
```

### 2. Configurar variables de entorno

Crea un archivo `.env` en la raíz del proyecto:

```env
GRIMMORY_URL=http://grimmory:61987
GRIMMORY_USERNAME=admin
GRIMMORY_PASSWORD=admin
QBIT_URL=http://qbittorrent:8080
QBIT_USERNAME=admin
QBIT_PASSWORD=adminadmin
JACKETT_URL=http://jackett:9117
JACKETT_API_KEY=tu_api_key_de_jackett
BOOKDROP_FOLDER=/bookdrop
POLL_INTERVAL=300
NETWORK_NAME=grimmory-network
NETWORK_INTERFACE=eth0
APP_IP=192.168.1.100
```

### 3. Iniciar los servicios

```bash
export $(cat .env | xargs) && docker compose up -d
```

### 4. Acceder a la aplicación

Abre `http://localhost` en tu navegador.

## Despliegue con Portainer

1. En Portainer, ve a **Stacks > Add stack**.
2. Selecciona **Repository** y apunta a `https://github.com/Jesuslconde/grimmory-book-manager`.
3. En **_env file**, pega el contenido de `stack.env` y ajusta los valores (especialmente `JACKETT_API_KEY`).
4. Despliega el stack.

## Configuración inicial

1. Ve a la pantalla de **Configuración** desde el dashboard.
2. Introduce las URLs y credenciales de Grimmory, qBittorrent y Jackett.
3. Usa el botón "Probar conexión" para verificar que cada servicio está accesible.
4. Configura la carpeta **Bookdrop** (donde qBittorrent guardará las descargas).

## Versiones

La versión se define en el archivo `VERSION` en la raíz del proyecto. El endpoint `GET /api/version` devuelve la versión actual.

Para generar una nueva release:

```bash
echo "1.1.0" > VERSION
git add VERSION
git commit -m "Bump version to 1.1.0"
git tag v1.1.0
git push origin main --tags
```

Para construir una imagen Docker con una versión específica:

```bash
APP_VERSION=1.1.0 docker compose build
```

## Desarrollo local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 80
```

## Licencia

MIT
