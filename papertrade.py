import alpaca_trade_api as tradeapi
import json
import yaml

class PaperTrade:

    def __init__(self):
        self.authorized=False
        with open("config.yaml", 'r') as ymlfile:
            self.cfg = yaml.load(ymlfile, Loader=yaml.FullLoader)
        self.api=tradeapi.REST(self.cfg['alpacaKey'], self.cfg['alpacaSecret'], self.cfg['alpacaURL'], api_version='v2')
      
    def GetPositions(self):
        return self.api.list_positions()

    def MarketStatus(self): 
        clock = self.api.get_clock()
        if clock.is_open:
            return True
        else:
            return False

    def GetMarketHours(self):
        clock = self.api.get_clock()
        return clock

    def GetStockPrice(self, stock):
        symbol_bars = self.api.get_barset(stock, 'minute', 1)
        symbol=symbol_bars[stock]
        price=symbol[0].c
        return price

    def GetOrderInfo(self, orderID):
        order = self.api.get_order_by_client_order_id(orderID)
        return order

    def AccountStatus(self):
        account = self.api.get_account()
        print(account.status)

    def AvailableMoney(self):
        account=self.api.get_account()
        return account.cash


    def IsTradeable(self, stock):
        # Check if AAPL is tradable on the Alpaca platform.
        try:
            asset = self.api.get_asset(str(stock))
            if asset.tradable:
                return True 
            else: 
                return False
        except Exception as e:
            return False

    def BuyStock(self, stock, quantity, orderType, customOrderID=None, price=None):
        if orderType=='limit' and customOrderID is not None:
            self.api.submit_order(
            symbol=str(stock),
            qty=quantity,
            side='buy',
            type=orderType,
            time_in_force='day',
            client_order_id=str(customOrderID),
            limit_price=price
            )
        elif orderType=='limit' and customOrderID is None:
            self.api.submit_order(
            symbol=str(stock),
            qty=quantity,
            side='buy',
            type=orderType,
            time_in_force='day',
            limit_price=price
            )
        elif orderType!='limit' and customOrderID is None:
            self.api.submit_order(
            symbol=str(stock),
            qty=quantity,
            side='buy',
            type=orderType,
            time_in_force='day'
            )
        elif orderType!='limit' and customOrderID is not None:
            self.api.submit_order(
            symbol=str(stock),
            qty=quantity,
            side='buy',
            type=orderType,
            time_in_force='day',
            client_order_id=str(customOrderID),
            )

    def SellStock(self, stock, quantity, orderType, customOrderID=None, price=None):
        if orderType=='limit' and customOrderID is not None:
            self.api.submit_order(
            symbol=str(stock),
            qty=quantity,
            side='sell',
            type=orderType,
            time_in_force='gtc',
            client_order_id=str(customOrderID),
            limit_price=price
            )
        elif orderType=='limit' and customOrderID is None:
            self.api.submit_order(
            symbol=str(stock),
            qty=quantity,
            side='sell',
            type=orderType,
            time_in_force='gtc',
            limit_price=price
            )
        elif orderType!='limit' and customOrderID is None:
            self.api.submit_order(
            symbol=str(stock),
            qty=quantity,
            side='sell',
            type=orderType,
            time_in_force='gtc'
            )
        elif orderType!='limit' and customOrderID is not None:
            self.api.submit_order(
            symbol=str(stock),
            qty=quantity,
            side='sell',
            type=orderType,
            client_order_id=str(customOrderID),
            time_in_force='gtc'
            )

    def CancelAll(self):
        self.api.cancel_all_orders()
            

    def CancelOrder(self, id):
        self.api.cancel_order(
            order_id=id
        )

