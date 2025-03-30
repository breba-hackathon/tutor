from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# Set up the Jinja2 environment
template_dir = Path(__file__).parent / "instructions"
env = Environment(loader=FileSystemLoader(template_dir))

template_dict = {}
for file_path in template_dir.iterdir():
    if file_path.is_file() and file_path.suffix == ".jinja2":
        template_name = file_path.stem
        template_dict[template_name] = env.get_template(file_path.name)

def get_instructions(name, **kwargs):
    template = template_dict[name]
    return template.render(**kwargs)

if __name__ == "__main__":
    instruction = get_instructions("test", topic="Hello there")
    expected = "This is a test of jinja templating Hello there"
    assert instruction == expected, f"Expected \"{expected}\", got \"{instruction}\""