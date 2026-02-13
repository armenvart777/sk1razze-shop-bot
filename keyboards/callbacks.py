from aiogram.filters.callback_data import CallbackData


class CategoryCB(CallbackData, prefix="cat"):
    id: int
    action: str = "view"


class ProductCB(CallbackData, prefix="prod"):
    id: int
    action: str = "view"


class PaginationCB(CallbackData, prefix="page"):
    target: str
    page: int


class PaymentMethodCB(CallbackData, prefix="pay"):
    method: str


class CryptoCurrencyCB(CallbackData, prefix="crypto"):
    currency: str


class AdminCategoryCB(CallbackData, prefix="acat"):
    id: int
    action: str


class AdminProductCB(CallbackData, prefix="aprod"):
    id: int
    action: str


class AdminPromoCB(CallbackData, prefix="apromo"):
    id: int
    action: str


class AdminTextCB(CallbackData, prefix="atxt"):
    key: str
    action: str = "edit"


class AdminConfirmCB(CallbackData, prefix="aconf"):
    action: str
    target: str = ""
    target_id: int = 0


class ProfileCB(CallbackData, prefix="prof"):
    action: str


class OrderCB(CallbackData, prefix="order"):
    id: int
    action: str = "view"


class AdminPanelCB(CallbackData, prefix="apanel"):
    section: str


class AdminNewsCB(CallbackData, prefix="anews"):
    id: int
    action: str


class SubscriptionCB(CallbackData, prefix="sub"):
    action: str = "check"


class OfferCB(CallbackData, prefix="offer"):
    action: str = "agree"


class MainMenuCB(CallbackData, prefix="menu"):
    action: str


class AdminSbpCB(CallbackData, prefix="asbp"):
    payment_id: int
    action: str  # "approve" or "reject"


class AdminFranchiseCB(CallbackData, prefix="afran"):
    id: int
    action: str


class FranchisePanelCB(CallbackData, prefix="fpanel"):
    action: str


class FranchiseProductCB(CallbackData, prefix="fprod"):
    id: int
    action: str


class NewsCB(CallbackData, prefix="news"):
    id: int
    action: str = "view"


class PrivateChannelCB(CallbackData, prefix="pch"):
    id: int
    action: str = "view"


class AdminPrivateChannelCB(CallbackData, prefix="apch"):
    id: int
    action: str


class FranchisePrivateChannelCB(CallbackData, prefix="fpch"):
    id: int
    action: str


class FranchiseSbpCB(CallbackData, prefix="fsbp"):
    payment_id: int
    action: str


class FranchiseOrderCB(CallbackData, prefix="ford"):
    id: int
    action: str = "view"


class WithdrawalCB(CallbackData, prefix="wdraw"):
    id: int = 0
    action: str = "menu"


class FranchiseBroadcastCB(CallbackData, prefix="fbcast"):
    franchise_id: int
    action: str  # "approve" or "reject"
