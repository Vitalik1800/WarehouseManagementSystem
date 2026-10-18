"""Stock writeoff GUI."""
from frontend.app.views._stock_outflow_view import StockOutflowView


class StockWriteoffsView(StockOutflowView):
    KIND = "writeoff"
    TITLE = "Списання товару"
    ACTION = "Підтвердити списання"
