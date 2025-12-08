from datetime import datetime
from dateutil.relativedelta import relativedelta

import asyncio
from faker import Faker


# In a real application, this would be a more robust credit card model
from ..schemas.subscription_schema import CardDetails

fake = Faker()


class MockBankService:
    async def process_payment(
        self, card_details: CardDetails, amount: float
    ) -> tuple[bool, str]:
        """
        Simulates processing a payment with a mock bank.

        Args:
            card_details: The credit card details.
            amount: The amount to charge.

        Returns:
            A tuple containing a boolean indicating success and the transaction ID.
        """
        await asyncio.sleep(1)  # Simulate network delay

        # Fail if the card number is a test "failure" card
        if card_details.card_number.endswith("0000"):
            return False, ""

        try:
            exp_month, exp_year_short = map(
                int, card_details.expiration_date.split("/")
            )
            exp_year = 2000 + exp_year_short

            # Create a datetime object for the first day of the month after the expiration month
            # This correctly handles cases where the current day is after the expiration day
            # but in the same month.
            expiration_date_obj = datetime(exp_year, exp_month, 1) + relativedelta(
                months=1
            )

            if datetime.now() >= expiration_date_obj:
                return False, ""
        # invalid expiration date format
        except ValueError:
            return False, ""

        # In a real scenario, you would interact with a payment gateway like Stripe
        # and get a real transaction ID.
        transaction_id = fake.uuid4()
        return True, transaction_id


mock_bank_service = MockBankService()
