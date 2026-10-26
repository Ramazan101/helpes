from django.contrib import admin
from .models import EquipmentCategory, Ticket, TicketComment, TicketHistory, TicketItem

admin.site.register(EquipmentCategory)
admin.site.register(Ticket)
admin.site.register(TicketItem)
admin.site.register(TicketComment)
admin.site.register(TicketHistory)
