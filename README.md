# Chat en Tiempo Real

Aplicación de chat en tiempo real basada en TCP socket con Python.

## Características

- **Protocolo**: TCP (conexión estable y confiable)
- **Identificación**: Hostname del sistema (automático)
- **Historial**: Mensajes guardados en archivo JSON
- **Múltiples clientes**: El servidor maneja conexiones simultáneas

## Requisitos

- Python 3.8+

## Estructura del Proyecto

```
1 Mensaje/
├── main.py           # Punto de entrada, selección cliente/servidor
├── server.py         # Lógica del servidor
├── client.py         # Lógica del cliente
├── requirements.txt  # Dependencias
└── README.md         # Instrucciones
```

## Instalación

No hay dependencias externas. Usa solo la biblioteca estándar de Python (`socket`).

## Uso

### Como Servidor

1. Ejecutar el servidor:
   ```bash
   python main.py --server
   ```

2. El servidor escucha en `localhost:5000`
3. Se identifica automáticamente por hostname del sistema
4. Todos los clientes conectados reciben mensajes

### Como Cliente

1. Ejecutar el cliente:
   ```bash
   python main.py --client
   ```

2. El cliente se conecta automáticamente a `localhost:5000`
3. Se identifica por su hostname
4. Muestra mensajes recibidos en tiempo real

## Historial de Mensajes

Los mensajes se guardan en `historial.json` con el siguiente formato:
```json
[
  {
    "timestamp": "2026-05-25 12:34:56",
    "hostname": "JAIRES2026",
    "message": "Hola mundo"
  }
]
```

## Ejemplo

```bash
# Terminal 1: Servidor
python main.py --server

# Terminal 2: Cliente 1
python main.py --client

# Terminal 3: Cliente 2
python main.py --client
```

Todos los clientes conectados verán los mensajes entre ellos.

## Deteniendo

Presiona `Ctrl+C` en la terminal donde se está ejecutando el programa.
