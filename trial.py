import sys
import matplotlib
matplotlib.use("Qt5Agg")

from PyQt5 import QtCore
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QApplication, QMainWindow, QMenu, QVBoxLayout, QSizePolicy, QMessageBox, QWidget

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.dates as mdates

from configparser import ConfigParser
import psycopg2 as pg
import numpy as np
import datetime



class MyMplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        # We want the axes cleared every time plot() is called
        #self.axes.hold(False)
        self.compute_initial_figure()

        FigureCanvas.__init__(self, self.fig)
        self.setParent(parent)
        FigureCanvas.setSizePolicy(self,
                               QSizePolicy.Expanding,
                               QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)

    def compute_initial_figure(self):
        pass

class MyDynamicMplCanvas(MyMplCanvas):
    #"""A canvas that updates itself every second with a new plot."""
    def __init__(self, *args, **kwargs):
        MyMplCanvas.__init__(self, *args, **kwargs)

        #timer = QtCore.QTimer(self)
        #timer.timeout.connect(self.connect)
        #timer.start(3000)
        self.filename   = 'database.ini'
        self.section    = 'postgresql'
        self.connect()

    def config(self):
        # create a parser
        parser = ConfigParser()
        # read config file
        parser.read(self.filename)

        # get section, default to postgresql
        db = {}
        if parser.has_section(self.section):
            params = parser.items(self.section)
            for param in params:
                db[param[0]] = param[1]
        else:
            raise Exception('Section {0} not found in the {1} file'.format(self.section, self.filename))

        return db

    def setYearlyParameters(self, datetimeValues):
        years = mdates.YearLocator()   # every year
        months = mdates.MonthLocator()  # every month
        tickFmt = mdates.DateFormatter('%Y')

        datemin = np.datetime64(datetimeValues[0], 'Y')
        datemax = np.datetime64(datetimeValues[-1], 'Y') + np.timedelta64(1, 'Y')

        return years, months, tickFmt, datemin, datemax

    def connect(self):
        # Initialize connection
        conn = None

        try:
            # read connection parameters
            params = self.config()

            # connect to the PostgreSQL server
            print('Connecting to the PostgreSQL database...')
            conn = pg.connect(**params)
            cur = conn.cursor()

            # read DB data into Pandas dataframe
            #self.df = pd.read_sql_query('SELECT * FROM p ORDER BY datep, timeut',
            #                       con = conn)
            query = "SELECT * FROM p ORDER BY datep, timeut"
            cur.execute(query)
            print("The number of parts: ", cur.rowcount)

            i = 0
            row = 1
            datet = np.zeros(cur.rowcount, dtype=datetime.datetime)
            ch_1 = np.zeros(cur.rowcount)

            while row is not None:
                row = cur.fetchone()
                if row is None:
                    break

                date, time, vec = row
                vec = np.array(vec, dtype=np.float)
                datet[i] = datetime.datetime.combine(date, time)
                vec[np.isnan(vec)] = 0
                # For the trial purposes ONLY the first channel is considered
                ch_1[i] = vec[0]
                i += 1

            self.axes.plot(datet.tolist(), ch_1.tolist(), 'r')

            months, days, tickFmt, datemin, datemax = self.setYearlyParameters(datet.tolist())

            # format the ticks
            self.axes.xaxis.set_major_locator(months)
            self.axes.xaxis.set_major_formatter(tickFmt)
            self.axes.xaxis.set_minor_locator(days)

            self.axes.set_xlim(datemin, datemax)

            self.axes.grid(True)

            # rotates and right aligns the x labels, and moves the bottom of the
            # axes up to make room for them
            self.fig.autofmt_xdate()
            self.draw()

            cur.close()

        except (Exception, pg.DatabaseError) as error:
            print(error)
        finally:
            if conn is not None:
                conn.close()
                print('Database connection closed.')


    # def update_figure(self, datet, vec):
#        X[:-1] = X[1:]
#        X[-1] = datet
#
#        Y[:-1] = Y[1:]
#        Y[-1] = vec

        # self.axes.plot(datet, vec, 'r')
        # self.draw()

class ApplicationWindow(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setWindowTitle("application main window")
        self.file_menu = QMenu('&File', self)
        self.file_menu.addAction('&Quit', self.fileQuit,
                         QtCore.Qt.CTRL + QtCore.Qt.Key_Q)
        self.menuBar().addMenu(self.file_menu)
        self.help_menu = QMenu('&Help', self)
        self.menuBar().addSeparator()
        self.menuBar().addMenu(self.help_menu)
        self.help_menu.addAction('&About', self.about)
        self.main_widget = QWidget(self)
        l = QVBoxLayout(self.main_widget)
        self.dc = MyDynamicMplCanvas(self.main_widget, width=5, height=4, dpi=100)
        #l.addWidget(sc)
        l.addWidget(self.dc)

        #self.scroll = QtWidgets.QScrollArea(self.main_widget)
        self.scroll = QtWidgets.QScrollBar(QtCore.Qt.Horizontal)
        #self.scroll.setWidget(dc)
        l.addWidget(self.scroll)
        self.scroll.setValue(99)
        self.step = .1
        self.setupSlider()

        self.main_widget.setFocus()
        self.setCentralWidget(self.main_widget)
        self.statusBar().showMessage("All hail matplotlib!", 2000)


    def setupSlider(self):
        self.lims = np.array(self.dc.axes.get_xlim())
        print("limit" + str(self.lims))
        self.scroll.setPageStep(self.step * 100)
        self.scroll.sliderReleased.connect(self.update)

        self.update()

    def update(self, evt=None):
        r = self.scroll.value() / ((1 + self.step) * 100)
        l1 = self.lims[0] + r * np.diff(self.lims)
        l2 = l1 + np.diff(self.lims) * self.step
        self.dc.axes.set_xlim(l1, l2)
        print(self.scroll.value(), l1, l2)
        self.dc.fig.canvas.draw_idle()

    def fileQuit(self):
        self.close()

    def closeEvent(self, ce):
        self.fileQuit()

    def about(self):
        QtWidgets.QMessageBox.about(self, "About",
                                    """embedding_in_qt5.py example
                                        Copyright 2005 Florent Rougon, 2006 Darren Dale, 2015 Jens H Nielsen

                                        This program is a simple example of a Qt5 application embedding matplotlib
                                        canvases.

                                        It may be used and modified with no restriction; raw copies as well as
                                        modified versions may be distributed without limitation.

                                        This is modified from the embedding in qt4 example to show the difference
                                        between qt4 and qt5"""
                                    )


if __name__ == '__main__':
    app = QApplication(sys.argv)
    aw = ApplicationWindow()
    aw.setWindowTitle("PyQt5 Matplot Example")
    aw.show()
    #sys.exit(qApp.exec_())
    app.exec_()
