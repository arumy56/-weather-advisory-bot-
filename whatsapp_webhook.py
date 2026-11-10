"""
WhatsApp Webhook Service for DWAS Weather Advisory
Compatible with Meta Cloud API & Twilio WhatsApp Sandbox.
Uses the same core advisory engine (advisory.py).
"""

import os
from typing import Any, Dict
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse
import httpx

from advisory import MSG, advise, forecast, geocode

load_dotenv()

app = FastAPI(
    title="DWAS WhatsApp Weather Advisory Webhook",
    description="Webhook backend for WhatsApp Cloud API & Twilio"
)

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "dwas_secret_token")


@app.get("/")
def root():
    return {"status": "ok", "service": "DWAS WhatsApp Weather Advisory"}


@app.get("/webhook")
def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """Meta WhatsApp Cloud API verification handshake."""
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification token mismatch")


async def send_whatsapp_message(recipient_id: str, text: str):
    """Send text reply via WhatsApp Cloud API."""
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        return

    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_id,
        "type": "text",
        "text": {"body": text}
    }
    async with httpx.AsyncClient() as client:
        await client.post(url, headers=headers, json=payload, timeout=10.0)


@app.post("/webhook")
async def handle_whatsapp_incoming(request: Request):
    """Handle incoming messages from Meta WhatsApp webhook."""
    body = await request.json()

    try:
        entries = body.get("entry", [])
        for entry in entries:
            for change in entry.get("changes", []):
                val = change.get("value", {})
                messages = val.get("messages", [])
                for msg in messages:
                    sender = msg.get("from")
                    msg_type = msg.get("type")

                    # Default language is Swahili or English based on keywords
                    lang = "en"

                    if msg_type == "text":
                        user_text = msg["text"]["body"].strip()
                        if user_text.lower() in ["hi", "hello", "start", "jambo"]:
                            await send_whatsapp_message(sender, MSG[lang]["welcome"])
                            continue

                        if user_text.lower().startswith("sw"):
                            lang = "sw"
                            user_text = user_text[2:].strip()

                        geo = await geocode(user_text)
                        if not geo:
                            await send_whatsapp_message(sender, MSG[lang]["notfound"].format(query=user_text))
                            continue

                        lat, lon, display_name = geo
                        data = await forecast(lat, lon)
                        reply = advise(data, lang=lang, location_name=display_name)
                        await send_whatsapp_message(sender, reply)

                    elif msg_type == "location":
                        loc = msg["location"]
                        lat = loc["latitude"]
                        lon = loc["longitude"]
                        data = await forecast(lat, lon)
                        label = f"Lat {lat:.2f}, Lon {lon:.2f}"
                        reply = advise(data, lang=lang, location_name=label)
                        await send_whatsapp_message(sender, reply)
    except Exception as exc:
        return {"status": "error", "message": str(exc)}

    return {"status": "received"}


@app.post("/twilio-webhook")
async def handle_twilio_webhook(request: Request):
    """Twilio WhatsApp webhook endpoint responding with TwiML."""
    form_data = await request.form()
    incoming_text = form_data.get("Body", "").strip()
    latitude = form_data.get("Latitude")
    longitude = form_data.get("Longitude")

    lang = "en"
    if incoming_text.lower().startswith("/sw"):
        lang = "sw"
        incoming_text = incoming_text.replace("/sw", "").strip()

    if latitude and longitude:
        data = await forecast(float(latitude), float(longitude))
        reply = advise(data, lang=lang, location_name=f"Lat {latitude}, Lon {longitude}")
    elif incoming_text:
        geo = await geocode(incoming_text)
        if not geo:
            reply = MSG[lang]["notfound"].format(query=incoming_text)
        else:
            lat, lon, display_name = geo
            data = await forecast(lat, lon)
            reply = advise(data, lang=lang, location_name=display_name)
    else:
        reply = MSG[lang]["welcome"]

    twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{reply}</Message></Response>'
    return Response(content=twiml, media_type="application/xml")
