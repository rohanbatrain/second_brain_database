import typer
from sbd_rohanbatrain.frontend.command_line_interface.sleep import sleep_app

# Main
app = typer.Typer(help="CLI App for Multiple Functionalities")

# Subapps

app.add_typer(sleep_app, name="sleep", help="Manage sleep logs.")




if __name__ == "__main__":
    app()