"""__main__ — `python -m kanban_app` 入口。"""

from kanban_app.app import App


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
