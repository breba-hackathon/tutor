from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# Set up the Jinja2 environment
template_dir = Path(__file__).parent / "instructions"
env = Environment(loader=FileSystemLoader(template_dir))


def get_instructions(name, **kwargs):
    template = env.get_template(f"{name}.jinja2")
    return template.render(**kwargs)

if __name__ == "__main__":
    instruction = get_instructions("test", topic="Hello there")
    expected = "This is a test of jinja templating Hello there"
    assert instruction == expected, f"Expected \"{expected}\", got \"{instruction}\""