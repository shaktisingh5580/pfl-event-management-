"""
tools/qr_tool.py
Generates QR codes for attendee tickets and certificate validation.
"""
import qrcode
from PIL import Image
from pathlib import Path
from config import OUTPUTS_DIR, EVENT_WEBSITE_URL


def generate_ticket_qr(attendee_id: str, attendee_name: str) -> Path:
    """
    Creates a QR code that encodes the attendee_id.
    When scanned at the gate, the check-in system looks up this ID.
    Returns the path of the saved QR PNG.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(attendee_id)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#1a1a2e", back_color="white")
    out_path = OUTPUTS_DIR / "tickets" / f"qr_{attendee_id}.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out_path))
    print(f"[QR] Ticket QR saved → {out_path}")
    return out_path


def generate_cert_validation_qr(cert_id: str, size: int = 120) -> Image.Image:
    """
    Creates a small QR code linking to the certificate verification page.
    Returns a PIL Image (not saved to disk) so it can be composited
    directly onto the certificate template by certificate_agent.py.
    """
    verify_url = f"{EVENT_WEBSITE_URL}/verify/{cert_id}" if EVENT_WEBSITE_URL else f"https://event.example.com/verify/{cert_id}"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=3,
        border=2,
    )
    qr.add_data(verify_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#1a1a2e", back_color="white").convert("RGB")
    img = img.resize((size, size), Image.LANCZOS)
    return img
