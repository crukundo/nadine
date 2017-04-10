import logging
from datetime import timedelta, date
from decimal import Decimal

from django.db import models
from django.db.models import F, Q, Count, Sum, Value
from django.db.models.functions import Coalesce
from django.utils.timezone import localtime, now
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.conf import settings

from nadine.models.membership import Membership

logger = logging.getLogger(__name__)

class BillManager(models.Manager):

    def unpaid(self, user=None, in_progress=None):
        query = self.filter(mark_paid=False)
        if user != None:
            query = query.filter(user=user)
        if in_progress != None:
            query = query.filter(in_progress=in_progress)
        query = query.annotate(owed=Sum('line_items__amount') - Sum('payment__paid_amount'), payment_count=Count('payment'))
        no_payments = Q(payment_count = 0)
        partial_payment = Q(owed__gt = 0)
        query = query.filter(no_payments | partial_payment)
        return query.order_by('due_date')


class UserBill(models.Model):
    objects = BillManager()
    created_ts = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="+", null=True, blank=True, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="bills", on_delete=models.CASCADE)
    membership = models.ForeignKey(Membership, related_name="bills", null=True, blank=True, on_delete=models.CASCADE)
    period_start = models.DateField()
    period_end = models.DateField()
    due_date = models.DateField()
    comment = models.TextField(blank=True, null=True)
    in_progress = models.BooleanField(default=False, blank=False, null=False)
    mark_paid = models.BooleanField(default=False, blank=False, null=False)

    def __unicode__(self):
        return "Bill %d" % self.id

    @property
    def total_paid(self):
        return self.payment_set.aggregate(paid=Coalesce(Sum('paid_amount'), Value(0.00)))['paid']

    @property
    def total_owed(self):
        return self.amount - self.total_paid

    @property
    def amount(self):
        return self.line_items.aggregate(amount=Coalesce(Sum('amount'), Value(0.00)))['amount']

    @property
    def is_paid(self):
        return self.mark_paid or self.total_owed <= 0

    @property
    def payment_date(self):
        # Date of the last payment
        last_payment = self.payments.order_by('payment_date').last()
        if last_payment:
            return last_payment.payment_date
        else:
            return None

    @models.permalink
    def get_absolute_url(self):
        return ('member:receipt', [], {'bill_id': self.id})

    @models.permalink
    def get_staff_url(self):
        return ('staff:billing:bill', [], {'bill_id': self.id})

    @models.permalink
    def get_admin_url(self):
        return ('admin:nadine_userbill_change', [self.id], {})

    # Not sure if I need this -- JLS
    # def non_refund_payments(self):
    #     return self.payments.filter(paid_amount__gt=0)
    #
    # Not sure if we need this either if we create them in the right order
    # and pull them ordering by ID
    # def ordered_line_items(self):
    #     # return bill line items with custom items last
    #     # custom items, then the fees
    #     line_items = self.line_items.filter(custom=False)
    #     custom_items = self.line_items.filter(custom=True)
    #     return list(line_items) + list(custom_items)
    #
    # def delete_non_custom_items(self):
    #     for i in self.line_items.filter(custom=False):
    #         i.delete()


class BillLineItem(models.Model):
    bill = models.ForeignKey(UserBill, related_name="line_items", null=True, on_delete=models.CASCADE)
    description = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    custom = models.BooleanField(default=False)

    def __unicode__(self):
        return self.description


class CoworkingDayLineItem(BillLineItem):
    days = models.ManyToManyField('CoworkingDay', related_name='bill_line')


class Payment(models.Model):
    bill = models.ForeignKey(UserBill, null=True, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE)
    payment_date = models.DateTimeField(auto_now_add=True)
    payment_service = models.CharField(max_length=200, blank=True, null=True, help_text="e.g., Stripe, Paypal, Dwolla, etc. May be empty")
    payment_method = models.CharField(max_length=200, blank=True, null=True, help_text="e.g., Visa, cash, bank transfer")
    paid_amount = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    transaction_id = models.CharField(max_length=200, null=True, blank=True)
    last4 = models.IntegerField(null=True, blank=True)

    def __unicode__(self):
        return "%s: %s - $%s" % (str(self.payment_date)[:16], self.user, self.paid_amount)
