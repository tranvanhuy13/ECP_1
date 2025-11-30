import stripe
from rest_framework import status
from rest_framework import permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from account.models import StripeModel, OrderModel
from rest_framework.decorators import permission_classes
from datetime import datetime


# stripe secret test key
import stripe
from django.conf import settings

stripe.api_key = settings.STRIPE_SECRET_KEY


def save_card_in_db(cardData, email, cardId, customer_id, user):

    # save card in django stripe model
    StripeModel.objects.create(
        email=email,
        customer_id=customer_id,
        card_number=cardData["number"],
        exp_month=cardData["exp_month"],
        exp_year=cardData["exp_year"],
        card_id=cardId,
        user=user,
    )


# Just for testing
class TestStripeImplementation(APIView):

    def post(self, request):
        test_payment_process = stripe.PaymentIntent.create(
            amount=120,
            currency="inr",
            payment_method_types=["card"],
            receipt_email="yash@gmail.com",
        )

        return Response(data=test_payment_process, status=status.HTTP_200_OK)


# check token expired or not
class CheckTokenValidation(APIView):

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response("Token is Valid", status=status.HTTP_200_OK)


# to create card token (to validate your card)
class CreateCardTokenView(APIView):

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        data = request.data
        email = data.get("email")
        token_id = data.get("token")
        cardStatus = data.get("save_card", False)

        if not token_id:
            return Response(
                {"detail": "Token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not email:
            return Response(
                {"detail": "Email is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Retrieve and verify the token from Stripe
            stripe_token = stripe.Token.retrieve(token_id)

            # Check if token was already used
            if stripe_token.used:
                return Response(
                    {"detail": "Token has already been used."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get card information from the token
            card_data = stripe_token.card
            last4 = card_data.last4
            exp_month = card_data.exp_month
            exp_year = card_data.exp_year
            brand = card_data.brand

            # Check if customer exists
            customer_data = stripe.Customer.list(email=email).data

            if len(customer_data) == 0:
                # Create new customer in Stripe with the card attached
                customer = stripe.Customer.create(
                    email=email,
                    description="Customer for card payment",
                    source=token_id,  # Attach the card using the token
                )
                # The card is now attached, retrieve it
                if customer.default_source:
                    created_card = stripe.Customer.retrieve_source(
                        customer.id,
                        customer.default_source
                    )
                else:
                    # Fallback: list sources and get the first one
                    sources = stripe.Customer.list_sources(customer.id, object='card', limit=1)
                    if sources.data:
                        created_card = sources.data[0]
                    else:
                        return Response(
                            {"detail": "Failed to attach card to customer."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        )

            else:
                # Customer exists - retrieve full customer object
                customer = stripe.Customer.retrieve(customer_data[0].id)
                
                # List all cards for this customer
                try:
                    customer_sources = stripe.Customer.list_sources(
                        customer.id,
                        object='card',
                        limit=100
                    )
                    existing_cards = customer_sources.data if customer_sources else []
                except:
                    existing_cards = []
                
                card_exists = False
                created_card = None
                
                # Check if the same card already exists
                for existing_card in existing_cards:
                    if (
                        existing_card.last4 == last4
                        and existing_card.exp_month == exp_month
                        and existing_card.exp_year == exp_year
                    ):
                        card_exists = True
                        created_card = existing_card
                        break
                
                if not card_exists:
                    # Add new card to existing customer
                    created_card = stripe.Customer.create_source(
                        customer.id,
                        source=token_id,
                    )

            # Save card to database if requested
            if cardStatus:
                try:
                    # Format card number with masking (XXXXXXXXXXXX + last4)
                    # Store as 16 characters for backward compatibility with UI
                    masked_card_number = "XXXXXXXXXXXX" + created_card.last4
                    
                    # Check if card already saved in database
                    existing_db_card = StripeModel.objects.filter(
                        card_number=masked_card_number, user=request.user
                    ).first()

                    if not existing_db_card:
                        StripeModel.objects.create(
                            email=email,
                            customer_id=customer.id,
                            card_number=masked_card_number,
                            exp_month=str(created_card.exp_month),
                            exp_year=str(created_card.exp_year),
                            card_id=created_card.id,
                            user=request.user,
                        )
                        save_message = "Card saved successfully"
                    else:
                        save_message = "Card already saved"

                except Exception as e:
                    return Response(
                        {
                            "detail": f"Error saving card to database: {str(e)}"
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # Return success response
            return Response(
                {
                    "customer_id": customer.id,
                    "email": email,
                    "card_data": {
                        "id": created_card.id,
                        "last4": created_card.last4,
                        "brand": created_card.brand,
                        "exp_month": created_card.exp_month,
                        "exp_year": created_card.exp_year,
                    },
                    "message": "Card processed successfully",
                },
                status=status.HTTP_200_OK,
            )

        except stripe.error.InvalidRequestError as e:
            return Response(
                {"detail": f"Invalid token provided: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except stripe.error.CardError as e:
            return Response(
                {"detail": e.user_message},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except stripe.error.APIConnectionError as e:
            return Response(
                {"detail": "Network error, Failed to establish a new connection."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            return Response(
                {"detail": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# Charge the customer card
class ChargeCustomerView(APIView):

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            data = request.data
            email = request.data["email"]
            customer_data = stripe.Customer.list(email=email).data
            customer = customer_data[0]

            customer_data = stripe.Customer.list(email=request.data["email"]).data

            # make stripe payment (charge the customer) (either use charge api or paymentIntent api)
            stripe.Charge.create(
                customer=customer_data[0],
                amount=int(float(request.data["amount"]) * 100),
                currency="inr",
                description="Software development services",  # required for Indian transactions
            )

            # saving order in django database
            new_order = OrderModel.objects.create(
                name=data["name"],
                card_number=data["card_number"],
                address=data["address"],
                ordered_item=data["ordered_item"],
                paid_status=data["paid_status"],
                paid_at=datetime.now(),
                total_price=data["total_price"],
                is_delivered=data["is_delivered"],
                delivered_at=data["delivered_at"],
                user=request.user,
            )

            return Response(
                data={
                    "data": {
                        "customer_id": customer.id,
                        "message": "Payment Successfull",
                    }
                },
                status=status.HTTP_200_OK,
            )

        except stripe.error.APIConnectionError:
            return Response(
                {"detail": "Network error, Failed to establish a new connection."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# retrieve card (to get user card details)
class RetrieveCardView(APIView):

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        card_details = stripe.Customer.retrieve_source(
            request.headers["Customer-Id"], request.headers["Card-Id"]
        )
        return Response(card_details, status=status.HTTP_200_OK)


# update a card
class CardUpdateView(APIView):

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        data = request.data
        update_card = stripe.Customer.modify_source(
            data["customer_id"],
            data["card_id"],
            exp_month=data["exp_month"] if data["exp_month"] else None,
            exp_year=data["exp_year"] if data["exp_year"] else None,
            name=data["name_on_card"] if data["name_on_card"] else None,
            address_city=data["address_city"] if data["address_city"] else None,
            address_country=(
                data["address_country"] if data["address_country"] else None
            ),
            address_state=data["address_state"] if data["address_state"] else None,
            address_zip=data["address_zip"] if data["address_zip"] else None,
        )

        # locating stripe object in django database
        obj = StripeModel.objects.get(card_number=request.data["card_number"])

        # updating stripe object in django database
        if obj:
            obj.name_on_card = (
                data["name_on_card"] if data["name_on_card"] else obj.name_on_card
            )
            obj.exp_month = data["exp_month"] if data["exp_month"] else obj.exp_month
            obj.exp_year = data["exp_year"] if data["exp_year"] else obj.exp_year
            obj.address_city = (
                data["address_city"] if data["address_city"] else obj.address_city
            )
            obj.address_country = (
                data["address_country"]
                if data["address_country"]
                else obj.address_country
            )
            obj.address_state = (
                data["address_state"] if data["address_state"] else obj.address_state
            )
            obj.address_zip = (
                data["address_zip"] if data["address_zip"] else obj.address_zip
            )
            obj.save()
        else:
            pass

        return Response(
            {
                "detail": "card updated successfully",
                "data": {"Updated Card": update_card},
            },
            status=status.HTTP_200_OK,
        )


# delete card
class DeleteCardView(APIView):

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        data = request.data
        obj_card = StripeModel.objects.get(card_number=request.data["card_number"])

        customerId = obj_card.customer_id
        cardId = obj_card.card_id

        # deleting card from stripe
        stripe.Customer.delete_source(customerId, cardId)

        # deleting card from django database
        obj_card.delete()

        # delete the customer
        # as deleting the card will not change the default card number on stripe therefore
        # we need to delete the customer (with a new card request customer will be recreated)
        stripe.Customer.delete(customerId)

        return Response("Card deleted successfully.", status=status.HTTP_200_OK)
