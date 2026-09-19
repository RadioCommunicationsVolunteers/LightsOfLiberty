import base64
import secrets
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal  # Added the container layout widget
from textual.reactive import reactive
from textual.widgets import Button, Header, Footer, Static, Label
import qrcode

class MaskedLabel(Horizontal):
    """A custom widget containing a masked label and a peek toggle button."""

    # Track whether the text is currently revealed or hidden
    revealed = reactive(False)

    def __init__(self, text: str, mask_char: str = "•", **kwargs):
        super().__init__(**kwargs)
        self.secret_text = text
        self.mask_char = mask_char

    def compose(self) -> ComposeResult:
        # Arrange the label and the button side-by-side
        with Horizontal():
            yield Label(self.masked_text, id="text-label")
            yield Button(" 🫣 Show", id="toggle-btn", variant="primary")

    @property
    def masked_text(self) -> str:
        """Returns the fully masked version of the secret text."""
        return self.mask_char * len(self.secret_text)

    def watch_revealed(self, revealed: bool) -> None:
        """Automatically updates the label and button when 'revealed' changes."""
        # Ensure widgets are mounted before attempting updates
        if not self.is_mounted:
            return

        label = self.query_one("#text-label", Label)
        button = self.query_one("#toggle-btn", Button)

        if revealed:
            label.update(self.secret_text)
            button.tooltip = "Hide"
            button.label = " 😨 Hide"
        else:
            label.update(self.masked_text)
            button.tooltip = "Show"
            button.label = " 🫣 Show"

    @on(Button.Pressed, "#toggle-btn")
    def handle_toggle(self) -> None:
        """Toggles the visibility state when the button is clicked."""
        self.revealed = not self.revealed


def generate_meshtastic_key():
    # 1. Generate 32 random bytes (256 bits)
    raw_bytes = secrets.token_bytes(32)
    
    # 2. Encode to Base64 URL-safe format
    b64_encoded = base64.urlsafe_b64encode(raw_bytes)
    
    # 3. Meshtastic keys do not use padding (=)
    meshtastic_key = b64_encoded.decode('utf-8').rstrip('=')
    
    return meshtastic_key

def generate_meshtastic_url(b64_key: str, channel_name="Custom", slot=1):
    """
    Generates a mock Meshtastic shared URL configuration.
    Real configurations use serialized Protocol Buffers.
    """
    assert b64_key is not None
    # Construct a valid Meshtastic application share link
    # Format: https://meshtastic.org/e/#<base64_protobuf_blob>
    # For demonstration, we encode a basic string pairing name and key
    config_string = f"name={channel_name}&key={b64_key}&slot={slot}"
    encoded_config = base64.urlsafe_b64encode(config_string.encode('utf-8')).decode('utf-8').rstrip('=')
    
    return f"https://meshtastic.org/e/#{encoded_config}"

def generate_terminal_qr(text: str) -> str:
    """Generates a text-based QR code suitable for terminal viewing."""
    qr = qrcode.QRCode(version=1, box_size=1, border=1)
    qr.add_data(text)
    qr.make(fit=True)
    
    # Render using special Unicode block characters for accurate spacing
    output = []
    matrix = qr.get_matrix()
    for r in range(0, len(matrix), 2):
        row_str = ""
        for c in range(len(matrix[0])):
            top = matrix[r][c]
            # Handle odd number of rows safely
            bottom = matrix[r+1][c] if (r+1) < len(matrix) else False
            
            if top and bottom:
                row_str += "█"
            elif top and not bottom:
                row_str += "▀"
            elif not top and bottom:
                row_str += "▄"
            else:
                row_str += " "
        output.append(row_str)
    
    return "\n".join(output)

class MeshtasticQRApp(App):
    """A Textual application that displays a Meshtastic configuration QR Code."""
    
    CSS = """
    MaskedLabel {
        height: auto;
        margin: 1 2;
        align: center middle;
    }
    
    #text-label {
        width: 40;
        padding: 1 2;
        background: $panel;
        border: tall $primary;
        color: #a6adc8;
    }
    
    #toggle-btn {
        margin-left: 1;
        min-width: 10;
    }
    
    Screen {
        align: center middle;
        background: #1e1e2e;
    }
    
    #container {
        width: 60;
        height: auto;
        border: solid #cba6f7;
        background: #11111b;
        padding: 1 2;
        align: center middle;
    }
    
    .title {
        text-align: center;
        text-style: bold;
        color: #cba6f7;
        margin-bottom: 1;
    }
    
    #qrcode {
        color: #cdd6f4;
        background: #11111b;
        content-align: center middle;
        margin: 1 0;
    }
    
    .url-text {
        text-align: center;
        color: #a6adc8;
    }
    """

    def compose(self) -> ComposeResult:
        # Generate 32 random bytes for a 256-bit AES key
        b64_key = generate_meshtastic_key()
        
        # Generate data
        url = generate_meshtastic_url(b64_key, "LightsOfLiberty", slot=1)
        qr_ascii = generate_terminal_qr(url)
        
        yield Header(name="Lights of Liberty")
        with Container(id="container"):
            yield Label("Meshtastic Channel QR Code", classes="title")
            yield Static(qr_ascii, id="qrcode")
            yield Label(f"URL: {url}", classes="url-text")
            yield MaskedLabel(text=b64_key)
        yield Footer()

if __name__ == "__main__":
    app = MeshtasticQRApp()
    app.run()
    
# # Generate and print the key
# key = generate_meshtastic_key()
# print(f"Your Meshtastic channel key:\n{key}")
