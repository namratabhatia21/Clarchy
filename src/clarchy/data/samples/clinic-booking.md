# CareSlot clinic booking

CareSlot lets patients book appointments at a network of 40 clinics in the United States.

Patients create an account, see available slots, book or cancel appointments, and pay a deposit by card at checkout. Clinic staff manage schedules from a web dashboard and export daily reports.

The system stores patient contact details and appointment history, so it must follow HIPAA: every access to patient data is audited, data is encrypted, and appointment and consent records are kept for 6 years. Backups must allow point-in-time restore.

We expect 120,000 registered patients and up to 80 requests per second at the Monday-morning peak. The booking service must be highly available with 99.95% uptime, and reminders go out by SMS and email the day before each appointment.

The team of 6 developers already has the booking backend in Docker containers. Budget is about $4,000 per month.
