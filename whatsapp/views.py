from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from twilio.twiml.messaging_response import MessagingResponse
from .models import UserSession, Area, Turf, Booking
from datetime import datetime, timedelta
from twilio.rest import Client
from django.conf import settings


SLOTS = [
    "6:00 AM - 7:00 AM",
    "7:00 AM - 8:00 AM",
    "8:00 AM - 9:00 AM",
    "6:00 PM - 7:00 PM",
    "7:00 PM - 8:00 PM",
]


@csrf_exempt
def whatsapp_webhook(request):

    raw_msg = request.POST.get("Body", "")
    incoming_msg = raw_msg.strip()
    phone = request.POST.get("From")

    session, _ = UserSession.objects.get_or_create(phone_number=phone)

    if not session.step:
        session.step = "search"
        session.save()

    resp = MessagingResponse()
    msg = resp.message()

    # ---------------- START ---------------- #
    if incoming_msg.lower() == "start":

        session.step = "search"
        session.selected_area = None
        session.selected_turf = None
        session.selected_date = None
        session.selected_slot = None
        session.save()

        msg.body("👋 *Welcome to TurfBot*\n\nType your Area name or Turf name")
        return HttpResponse(str(resp), content_type="application/xml")

    # ---------------- SEARCH ---------------- #
    if session.step == "search":

        turf_obj = Turf.objects.filter(name__iexact=incoming_msg).first()

        if turf_obj:
            session.selected_area = turf_obj.area.name
            session.selected_turf = turf_obj.name
            session.step = "date"
            session.save()

        else:
            area_obj = Area.objects.filter(name__iexact=incoming_msg).first()

            if area_obj:
                session.selected_area = area_obj.name
                session.step = "turf_list"
                session.save()

                turfs = Turf.objects.filter(area=area_obj)

                text = f"🏟️ *Turfs in {area_obj.name}*\n\n"
                for i, turf in enumerate(turfs, start=1):
                    text += f"{i}. {turf.name}\n"

                text += "\nReply with turf number"
                msg.body(text)
                return HttpResponse(str(resp), content_type="application/xml")

            msg.body("❌ Area or Turf not found.")
            return HttpResponse(str(resp), content_type="application/xml")

    # ---------------- TURF LIST ---------------- #
    if session.step == "turf_list":

        turfs = list(Turf.objects.filter(area__name=session.selected_area))

        if not incoming_msg.isdigit():
            msg.body("❌ Reply with valid turf number")
            return HttpResponse(str(resp), content_type="application/xml")

        index = int(incoming_msg) - 1

        if index < 0 or index >= len(turfs):
            msg.body("❌ Invalid turf number")
            return HttpResponse(str(resp), content_type="application/xml")

        session.selected_turf = turfs[index].name
        session.step = "date"
        session.save()

    # ---------------- DATE PICKER ---------------- #
    if session.step == "date":

        today = datetime.today().date()
        text = f"📅 *Select Date – {session.selected_turf}*\n\n"

        for i in range(7):
            next_date = today + timedelta(days=i)
            text += f"{i+1}. {next_date.strftime('%d %b %Y')}\n"

        text += "\nReply with date number\nType 0 to go back"

        session.step = "date_select"
        session.save()

        msg.body(text)
        return HttpResponse(str(resp), content_type="application/xml")

    # ---------------- DATE SELECT ---------------- #
    if session.step == "date_select":

        if incoming_msg == "0":
            session.step = "search"
            session.selected_area = None
            session.selected_turf = None
            session.selected_date = None
            session.selected_slot = None
            session.save()

            msg.body("🔙 Back to Area Selection\n\nType your Area name or Turf name")
            return HttpResponse(str(resp), content_type="application/xml")

        if not incoming_msg.isdigit():
            msg.body("❌ Reply with valid date number\nType 0 to go back")
            return HttpResponse(str(resp), content_type="application/xml")

        index = int(incoming_msg) - 1

        if index < 0 or index > 6:
            msg.body("❌ Invalid date number\nType 0 to go back")
            return HttpResponse(str(resp), content_type="application/xml")

        session.selected_date = datetime.today().date() + timedelta(days=index)
        session.step = "slot"
        session.save()

    # ---------------- SLOT LIST ---------------- #
    if session.step == "slot":

        booked_slots = Booking.objects.filter(
            turf=session.selected_turf,
            date=session.selected_date
        )

        text = f"🕒 *Available Slots*\n"
        text += f"📅 {session.selected_date.strftime('%d %b %Y')}\n\n"

        for i, slot in enumerate(SLOTS, start=1):

            is_booked = False
            for booking in booked_slots:
                if slot in booking.slot.split(","):
                    is_booked = True
                    break

            if is_booked:
                text += f"{i}. ❌ {slot}\n"
            else:
                text += f"{i}. ✅ {slot}\n"

        text += "\nReply with slot numbers (Example: 1 or 1,2)\nType 0 to go back"

        session.step = "slot_select"
        session.save()

        msg.body(text)
        return HttpResponse(str(resp), content_type="application/xml")

    # ---------------- SLOT SELECT ---------------- #
    if session.step == "slot_select":

        if incoming_msg == "0":
            session.step = "date"
            session.save()
            return HttpResponse(str(resp), content_type="application/xml")

        slot_numbers = [x.strip() for x in incoming_msg.split(",")]

        if not all(num.isdigit() for num in slot_numbers):
            msg.body("❌ Enter like 1 or 1,2\nType 0 to go back")
            return HttpResponse(str(resp), content_type="application/xml")

        indexes = sorted([int(num) - 1 for num in slot_numbers])

        if any(i < 0 or i >= len(SLOTS) for i in indexes):
            msg.body("❌ Invalid slot number\nType 0 to go back")
            return HttpResponse(str(resp), content_type="application/xml")

        for i in range(len(indexes) - 1):
            if indexes[i+1] != indexes[i] + 1:
                msg.body("❌ Select continuous slots only (Example: 1,2,3)")
                return HttpResponse(str(resp), content_type="application/xml")

        selected_slots = [SLOTS[i] for i in indexes]

        existing = Booking.objects.filter(
            turf=session.selected_turf,
            date=session.selected_date
        )

        for booking in existing:
            booked_list = booking.slot.split(",")
            if any(slot in booked_list for slot in selected_slots):
                msg.body("❌ One or more selected slots already booked.")
                return HttpResponse(str(resp), content_type="application/xml")

        session.selected_slot = ",".join(selected_slots)
        session.step = "confirm_booking"
        session.save()

        slot_display = "\n".join(selected_slots)

        msg.body(
            f"⚠️ *Confirm Booking?*\n\n"
            f"🏟️ {session.selected_turf}\n"
            f"📅 {session.selected_date.strftime('%d %b %Y')}\n"
            f"🕒 {slot_display}\n\n"
            "Reply YES to confirm\n"
            "Reply NO to change slot\n"
            "Type 0 to go back"
        )

        return HttpResponse(str(resp), content_type="application/xml")

    # ---------------- CONFIRM BOOKING ---------------- #
    if session.step == "confirm_booking":

        if incoming_msg.lower() == "yes":

            Booking.objects.create(
                area=session.selected_area,
                turf=session.selected_turf,
                date=session.selected_date,
                slot=session.selected_slot,
                phone_number=session.phone_number
            )

            # GET OWNER PHONE
            turf_obj = Turf.objects.get(name=session.selected_turf)
            owner_phone = turf_obj.owner_phone

            # SEND MESSAGE TO OWNER
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

            owner_message = (
                f"📢 *New Turf Booking*\n\n"
                f"🏟️ Turf: {session.selected_turf}\n"
                f"📅 Date: {session.selected_date}\n"
                f"🕒 Slots: {session.selected_slot}\n"
                f"📱 Customer: {session.phone_number}"
            )

            client.messages.create(
                body=owner_message,
                from_=settings.TWILIO_WHATSAPP_NUMBER,
                to=f"whatsapp:+{owner_phone}"
            )

            session.step = "search"
            session.save()

            msg.body("💰 ✅ Booking Confirmed! Enjoy your game!\n\nType START to book again.")
            return HttpResponse(str(resp), content_type="application/xml")

        elif incoming_msg.lower() == "no":
            session.step = "slot"
            session.save()
            return HttpResponse(str(resp), content_type="application/xml")

    msg.body("Type START to begin.")
    return HttpResponse(str(resp), content_type="application/xml")