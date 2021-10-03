import random
from os import environ
from PyQt5.QtGui import QImage, QPixmap, QColor, QBrush, QPen
from PyQt5.QtWidgets import QGraphicsPixmapItem, QGraphicsItem, QGraphicsRectItem, QMainWindow, QGraphicsView, QGraphicsScene, QAction, QMessageBox, QApplication
from PyQt5.QtCore import QSize, QRect, pyqtSignal, QObject, QRectF, QPointF, Qt
import os


# Setting global variables 
win_w_h = 1000, 700  # window's width and height. 
card_spacer_x = 130  # distance between cards (x).
g_offset_x = 50  # global offset of x. 
g_offset_y = 50  # global offset of y. 
face_side = 0  # face side of a card.
back_side = 1  # back side of a card.
suits = ["C", "S", "H", "D"]  # suits of a cards.

def suppress_qt_warnings():
    environ["QT_DEVICE_PIXEL_RATIO"] = "0"
    environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    environ["QT_SCREEN_SCALE_FACTORS"] = "1"
    environ["QT_SCALE_FACTOR"] = "1"


class Signals(QObject):
    '''
    This class implements signals initialization.
    '''
    complete = pyqtSignal()
    clicked = pyqtSignal()


class Card(QGraphicsPixmapItem):
    '''
    This class implements card creation including its properties image and other
    necessary functional.
    '''
    def __init__(self, value, suit, *args, **kwargs):
        super(Card, self).__init__(*args, **kwargs)
        self.signals = Signals()
        self.stack = None  # Stack this card currently is in.
        self.child = None  # Card stacked on this one (for work deck).
        # Store the value & suit of the cards internal to it.
        self.value = value
        self.suit = suit
        self.side = None
        # Cards have no internal transparent areas, so we can use this faster method.
        self.setShapeMode(QGraphicsPixmapItem.BoundingRectShape)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.load_images()

    # Loading images of cards (face and back)
    def load_images(self):
        self.face = QPixmap(os.path.join('images/cards', '%s%s.png' % (self.value, self.suit)))
        self.back = QPixmap(os.path.join('images', 'card_back.png'))

    def turn_face_up(self):
        self.side = face_side
        self.setPixmap(self.face)

    def turn_back_up(self):
        self.side = back_side
        self.setPixmap(self.back)

    @property
    def is_face_up(self):
        return self.side == face_side

    @property
    def color(self):
        return 'r' if self.suit in ('H', 'D') else 'b'

    def mousePressEvent(self, e):
        if not self.is_face_up and self.stack.cards[-1] == self:
            self.turn_face_up()  # We can do this without checking.
            e.accept()
            return

        if self.stack and not self.stack.is_free_card(self):
            e.ignore()
            return

        self.stack.setZValue(1000)  # activate (move to top layer).
        e.accept()
        super(Card, self).mouseReleaseEvent(e)

    def mouseReleaseEvent(self, e):
        self.stack.setZValue(-1)  # deactivate (move to top layer).

        items = self.collidingItems()
        if items:
            # Find the topmost item from a different stack:
            for item in items:
                if ((isinstance(item, Card) and item.stack != self.stack) or
                    (isinstance(item, Stack) and item != self.stack)):

                    if item.stack.is_valid_drop(self):
                        # Remove card + all children from previous stack, add to the new.
                        # Note: the only place there will be children is on a workstack.
                        cards = self.stack.remove_card(self)
                        item.stack.add_cards(cards)
                        break

        # Refresh this card's stack, pulling it back if it was dropped.
        self.stack.update()
        super(Card, self).mouseReleaseEvent(e)

class Stack(QGraphicsRectItem):
    '''
    This class implements setting cards on the deck, adding/removing cards and
    also checking status of card (free/dropable).
    '''
    def __init__(self, *args, **kwargs):
        super(Stack, self).__init__(*args, **kwargs)

        self.setRect(QRectF(QRect(0, 0, 80, 116)))
        self.setZValue(-1)
        # Cards on this deck, in order.
        self.cards = []
        # Store a self ref, so the collision logic can handle cards and
        # stacks with the same approach.
        self.stack = self
        self.setup()
        self.reset()

    def setup(self):
        pass

    def reset(self):
        self.remove_all_cards()

    def update(self):
        for n, card in enumerate(self.cards):
            card.setPos( self.pos() + QPointF(n * self.offset_x, n * self.offset_y))
            card.setZValue(n)

    def add_card(self, card, update=True):
        card.stack = self
        self.cards.append(card)
        if update:
            self.update()

    def add_cards(self, cards):
        for card in cards:
            self.add_card(card, update=False)
        self.update()

    def remove_card(self, card):
        card.stack = None
        self.cards.remove(card)
        self.update()
        return [card] # Returns a list, as WorkStack must return children

    def remove_all_cards(self):
        for card in self.cards[:]:
            card.stack = None
        self.cards = []

    def is_valid_drop(self, card):
        return True

    def is_free_card(self, card):
        return False


class Deck(Stack):
    '''
    This class implements cards stacking into the deck, restaking and taking 
    a top card from the list of cards.
    '''
    offset_x = -0.2
    offset_y = -0.3
    restack_counter = 0

    def reset(self):
        super(Deck, self).reset()
        self.restack_counter = 0
        self.set_color(Qt.green)

    def stack_cards(self, cards):
        for card in cards:
            self.add_card(card)
            card.turn_back_up()

    def can_restack(self, n_rounds=3):
        return n_rounds is None or self.restack_counter < n_rounds-1

    def update_stack_status(self, n_rounds):
        if not self.can_restack(n_rounds):
            self.set_color(Qt.red)
        else:
            # We only need this if players change the round number during a game.
            self.set_color(Qt.green)

    def restack(self, fromstack):
        self.restack_counter += 1
        # We need to slice as we're adding to the list, reverse to stack back
        # in the original order.
        for card in fromstack.cards[::-1]:
            fromstack.remove_card(card)
            self.add_card(card)
            card.turn_back_up()

    def take_top_card(self):
        try:
            card = self.cards[-1]
            self.remove_card(card)
            return card
        except IndexError:
            pass

    def set_color(self, color):
        color = QColor(color)
        color.setAlpha(50)
        brush = QBrush(color)
        self.setBrush(brush)
        self.setPen(QPen(Qt.NoPen))

    def is_valid_drop(self, card):
        return False


class Deal(Stack):
    '''
    This class implements a start of a new game. 
    '''
    offset_x = 20
    offset_y = 0
    spread_from = 0

    def setup(self):
        self.setPen(QPen(Qt.NoPen))
        color = QColor(Qt.black)
        color.setAlpha(50)
        brush = QBrush(color)
        self.setBrush(brush)

    def reset(self):
        super(Deal, self).reset()
        self.spread_from = 0  # Card index to start spreading cards out.

    def is_valid_drop(self, card):
        return False

    def is_free_card(self, card):
        return card == self.cards[-1]

    def update(self):
        # Only spread the top 3 cards
        offset_x = 0
        for n, card in enumerate(self.cards):
            card.setPos(self.pos() + QPointF(offset_x, 0))
            card.setZValue(n)

            if n >= self.spread_from:
                offset_x = offset_x + self.offset_x


class Work(Stack):
    '''
    This class implements working stack setup process including adding and 
    removing card. 
    '''
    offset_x = 0
    offset_y = 15
    offset_y_back = 5

    def setup(self):
        self.setPen(QPen(Qt.NoPen))
        color = QColor(Qt.black)
        color.setAlpha(50)
        brush = QBrush(color)
        self.setBrush(brush)

    def is_valid_drop(self, card):
        if not self.cards:
            return True

        if (card.color != self.cards[-1].color and
            card.value == self.cards[-1].value -1):
            return True

        return False

    def is_free_card(self, card):
        return card.is_face_up #self.cards and card == self.cards[-1]

    def add_card(self, card, update=True):
        if self.cards:
            card.setParentItem(self.cards[-1])
        else:
            card.setParentItem(self)

        super(Work, self).add_card(card, update=update)

    def remove_card(self, card):
        index = self.cards.index(card)
        self.cards, cards = self.cards[:index], self.cards[index:]

        for card in cards:
            # Remove card and all children, returning a list of cards removed in order.
            card.setParentItem(None)
            card.stack = None

        self.update()
        return cards

    def remove_all_cards(self):
        for card in self.cards[:]:
            card.setParentItem(None)
            card.stack = None
        self.cards = []

    def update(self):
        self.stack.setZValue(-1) # Reset this stack the the background.
        # Only spread the top 3 cards
        offset_y = 0
        for n, card in enumerate(self.cards):
            card.setPos(QPointF(0, offset_y))

            if card.is_face_up:
                offset_y = self.offset_y
            else:
                offset_y = self.offset_y_back


class Drop(Stack):
    '''
    This class implements drop stack setup process including adding and 
    removing card. 
    '''
    offset_x = -0.2
    offset_y = -0.3

    suit = None
    value = 0

    def setup(self):
        self.signals = Signals()
        color = QColor(Qt.blue)
        color.setAlpha(50)
        pen = QPen(color)
        pen.setWidth(5)
        self.setPen(pen)

    def reset(self):
        super(Drop, self).reset()
        self.suit = None
        self.value = 0

    def is_valid_drop(self, card):
        if ((self.suit is None or card.suit == self.suit) and
                (card.value == self.value + 1)):
            return True

        return False

    def add_card(self, card, update=True):
        super(Drop, self).add_card(card, update=update)
        self.suit = card.suit
        self.value = self.cards[-1].value

        if self.is_complete:
            self.signals.complete.emit()

    def remove_card(self, card):
        super(Drop, self).remove_card(card)
        self.value = self.cards[-1].value if self.cards else 0

    @property
    def is_complete(self):
        return self.value == 13


class Trigger(QGraphicsRectItem):
    '''
    This class implements trigger (signal + mouse press event) while user click 
    on menubar and then click "New Game".
    '''
    def __init__(self, *args, **kwargs):
        super(Trigger, self).__init__(*args, **kwargs)
        self.setRect(QRectF(QRect(30, 30, 110, 140)))
        self.setZValue(1000)
        pen = QPen(Qt.NoPen)
        self.setPen(pen)
        self.signals = Signals()

    def mousePressEvent(self, e):
        self.signals.clicked.emit()

class MainWindow(QMainWindow):
    '''
    This class implements creation of the main window UI. 
    It also setting up working, dropping and deal locations for cards and
    generating them.
    '''
    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)

        view = QGraphicsView()
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(QRectF(0, 0, *win_w_h))

        felt = QBrush(QPixmap(os.path.join('images','background.jpg')))
        self.scene.setBackgroundBrush(felt)

        view.setScene(self.scene)

        menu = self.menuBar().addMenu("&Settings")

        deal_action = QAction("New Game", self)
        deal_action.triggered.connect(self.restart_game)
        menu.addAction(deal_action)

        menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit)
        menu.addAction(quit_action)

        self.deck = []
        self.deal_n = 1  # Number of cards to deal each time
        self.rounds_n = None  # Number of rounds (restacks) before end.

        for suit in suits:
            for value in range(1, 14):
                card = Card(value, suit)
                self.deck.append(card)
                self.scene.addItem(card)

        self.setCentralWidget(view)
        self.setFixedSize(*win_w_h)

        self.deckstack = Deck()
        self.deckstack.setPos(g_offset_x , g_offset_y)
        self.scene.addItem(self.deckstack)

        # Set up the working locations.
        self.works = []
        for n in range(7):
            stack = Work()
            stack.setPos(g_offset_x + card_spacer_x*n, 200)
            self.scene.addItem(stack)
            self.works.append(stack)

        self.drops = []

        # Set up the drop locations.
        for n in range(4):
            stack = Drop()
            stack.setPos(g_offset_x + card_spacer_x * (3+n), g_offset_y)
            stack.signals.complete.connect(self.check_win_condition)

            self.scene.addItem(stack)
            self.drops.append(stack)

        # Add the deal location.
        self.dealstack = Deal()
        self.dealstack.setPos(g_offset_x + card_spacer_x, g_offset_y)
        self.scene.addItem(self.dealstack)

        # Add the deal click-trigger.
        dealtrigger = Trigger()
        dealtrigger.signals.clicked.connect(self.deal)
        self.scene.addItem(dealtrigger)

        self.shuffle_and_stack()

        self.setWindowTitle("Solitaire")
        self.show()

    def restart_game(self):
        reply = QMessageBox.question(self, "Deal again", "Are you sure you want to start a new game?",
                                    QMessageBox.Yes | QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.shuffle_and_stack()

    def quit(self):
        self.close()

    def set_deal_n(self):
        self.deal_n = 1

    def set_rounds_n(self):
        self.rounds_n = None  # setting unlimited rounds.
        self.deckstack.update_stack_status(self.rounds_n)

    def shuffle_and_stack(self):
        # Remove cards from all stacks.
        for stack in [self.deckstack, self.dealstack] + self.drops + self.works:
            stack.reset()

        random.shuffle(self.deck)

        # Deal out from the top of the deck, turning over the
        # final card on each line.
        cards = self.deck[:]
        for n, workstack in enumerate(self.works, 1):
            for a in range(n):
                card = cards.pop()
                workstack.add_card(card)
                card.turn_back_up()
                if a == n-1:
                    card.turn_face_up()

        # Ensure removed from all other stacks here.
        self.deckstack.stack_cards(cards)

    def deal(self):
        if self.deckstack.cards:
            self.dealstack.spread_from = len(self.dealstack.cards)
            for n in range(self.deal_n):
                card = self.deckstack.take_top_card()
                if card:
                    self.dealstack.add_card(card)
                    card.turn_face_up()

        elif self.deckstack.can_restack(self.rounds_n):
            self.deckstack.restack(self.dealstack)
            self.deckstack.update_stack_status(self.rounds_n)

    def auto_drop_card(self, card):
        for stack in self.drops:
            if stack.is_valid_drop(card):
                card.stack.remove_card(card)
                stack.add_card(card)
                break

    def check_win_condition(self):
        complete = all(s.is_complete for s in self.drops)
        if complete:
            answer = QMessageBox.question(self, "Congratulations! You won!", 
            "Do you want to start a new game?", QMessageBox.Yes | QMessageBox.No)

            if answer == QMessageBox.Yes:
                self.shuffle_and_stack()

if __name__ == '__main__':
    suppress_qt_warnings()
    app = QApplication([])
    window = MainWindow()
    app.exec_()
