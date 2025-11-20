import stripe
from rest_framework import status
from rest_framework import permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from account.models import StripeModel, OrderModel
from rest_framework.decorators import permission_classes
from datetime import datetime


# stripe secret test key
stripe.api_key="your secret key here"


def save_card_in_db(cardData, email, cardId, customer_id, user):

    # save card in django stripe model
    StripeModel.objects.create(
        email = email,
        customer_id = customer_id,
        card_number=cardData["number"],
        exp_month = cardData["exp_month"],
        exp_year = cardData["exp_year"],
        card_id = cardId,
        user = user,
    )
