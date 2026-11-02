"""Build a standalone Blender add-on ZIP without assets or external paths."""
from pathlib import Path
import ast
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def build(destination=None):
    module = ast.parse((ROOT / "addon/mmd_outfit/jobs.py").read_text(encoding="utf-8"))
    version = next(ast.literal_eval(node.value) for node in module.body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == "VERSION" for target in node.targets))
    destination = Path(destination or ROOT / "dist" / f"mmd_outfit_bridge-{version}.zip")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((ROOT / "addon" / "mmd_outfit").glob("*.py")):
            archive.write(path, "mmd_outfit/" + path.name)
        for name in ('PPF_APACHE_LICENSE.txt', 'THIRD_PARTY_NOTICES.md'):
            archive.write(ROOT / 'addon' / 'mmd_outfit' / name, 'mmd_outfit/' + name)
        for path in sorted((ROOT / "src").glob("*.py")):
            if path.name not in {"cli.py", "blender_env.py"}:
                archive.write(path, "mmd_outfit/engine/" + path.name)
        archive.write(ROOT / "addon" / "README.md", "mmd_outfit/README.md")
        native_doc=ROOT/'docs/STOCKINGS_SLEEVES_2026-10-26.md'
        if native_doc.is_file():archive.write(native_doc,'mmd_outfit/NATIVE_REPAIR.md')
        pitfalls=ROOT/'docs'/'KNOWN_PITFALLS_2026-10-26.md'
        if pitfalls.is_file():archive.write(pitfalls,'mmd_outfit/KNOWN_PITFALLS.md')
        for filename in ('STOCKINGS_SLEEVES_2026-10-26.md','KNOWN_PITFALLS_2026-10-26.md','CYNICAL_CLOTH_15S_2026-10-26.md','CLOTHING_WRINKLE_RESEARCH_2026-10-26.md','STRUCTURED_CLOTH_REPAIR_2026-10-27.md','CHEST_REPAIR_HD_2026-10-27.md','SLEEVE_13S_REPAIR_2026-10-27.md','DYNAMIC_CONTACT_RESEARCH_2026-10-27.md'):
            source=ROOT/'docs'/filename
            if source.is_file():archive.write(source,'mmd_outfit/'+filename)
    print(destination)
    return destination


if __name__ == "__main__":
    build()
