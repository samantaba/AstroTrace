import sys
from PyQt5.QtWidgets import QApplication
from ui import SDRMainWindow

if __name__ == "__main__":
    # Create the Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("AstroTrace")
    app.setApplicationDisplayName("AstroTrace")
    app.setOrganizationName("AstroTrace")
    app.setOrganizationDomain("astrotrace.local")
    # Initialize main window
    main_window = SDRMainWindow()
    main_window.show()
    # Execute the application event loop
    sys.exit(app.exec_())
