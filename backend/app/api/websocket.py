from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
import asyncio
from app.services.sensor.ingestion import sensor_ingestion_service
from app.core.logger import get_logger
from app.schemas.sensor import SensorPacket

logger = get_logger("WebSocketManager")
ws_router = APIRouter()

@ws_router.websocket("/ws/live")
async def websocket_live_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Client connected to /ws/live WebSocket.")
    q = await sensor_ingestion_service.subscribe()
    
    # Send immediate initial diagnostic state
    initial_diag = sensor_ingestion_service.get_diagnostic_status()
    await websocket.send_text(json.dumps({
        "type": "STATUS_UPDATE",
        "data": initial_diag
    }))

    try:
        while True:
            # Receive incoming messages from client (e.g. heartbeat or live sensor packet from bridge)
            recv_task = asyncio.create_task(websocket.receive_text())
            queue_task = asyncio.create_task(q.get())

            done, pending = await asyncio.wait(
                [recv_task, queue_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in pending:
                task.cancel()

            if recv_task in done:
                try:
                    client_msg = recv_task.result()
                    parsed = json.loads(client_msg)
                    msg_type = parsed.get("type")
                    
                    if msg_type == "PING":
                        await websocket.send_text(json.dumps({"type": "PONG", "timestamp": parsed.get("timestamp")}))
                    elif msg_type == "SENSOR_PACKET":
                        # Direct WebSocket ingestion from an ESP32 or client bridge
                        packet = SensorPacket.model_validate(parsed.get("data", {}))
                        sensor_ingestion_service.process_packet(packet.model_dump())
                except WebSocketDisconnect:
                    raise
                except Exception as e:
                    logger.warning(f"Error handling WebSocket client message: {e}")

            if queue_task in done:
                stream_sample = queue_task.result()
                await websocket.send_text(json.dumps({
                    "type": "SENSOR_SAMPLE",
                    "data": stream_sample
                }))

    except WebSocketDisconnect:
        logger.info("Client disconnected from /ws/live.")
    except Exception as e:
        logger.error(f"WebSocket exception: {e}")
    finally:
        sensor_ingestion_service.unsubscribe(q)
