import sys
from streamlit.web import cli as stcli

APP_PATH = "dav_tool/ui/app.py"


def main():
    sys.argv = ["streamlit", "run", APP_PATH, *sys.argv[1:]]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
