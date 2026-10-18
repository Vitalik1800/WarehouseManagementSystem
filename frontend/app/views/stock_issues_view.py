"""Stock issue GUI."""
from frontend.app.views._stock_outflow_view import StockOutflowView


class StockIssuesView(StockOutflowView):
    KIND = "issue"
    TITLE = "Видача товару"
    ACTION = "Підтвердити видачу"
