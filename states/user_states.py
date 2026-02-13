from aiogram.fsm.state import State, StatesGroup


class TopupStates(StatesGroup):
    choosing_method = State()
    choosing_currency = State()
    entering_amount = State()
    waiting_payment = State()
    waiting_sbp_receipt = State()


class PromoStates(StatesGroup):
    entering_code = State()
