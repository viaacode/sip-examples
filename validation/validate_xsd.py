from pathlib import Path
from itertools import chain

from xmlschema import XMLSchema

premis_xsd = XMLSchema("validation/premis.xsd.xml")
mets_xsd = XMLSchema("validation/mets.xsd.xml")
mods_xsd = XMLSchema("validation/mods-3-7.xsd.xml")


def validate_xsd(path: Path):
    premis_files = path.rglob("premis.xml")
    mets_files = path.rglob("METS.xml")
    mods_files = path.rglob("mods.xml")

    premis_valid = ((premis_xsd.is_valid(file), file) for file in premis_files)
    mets_valid = ((mets_xsd.is_valid(file), file) for file in mets_files)
    mods_valid = ((mods_xsd.is_valid(file), file) for file in mods_files)

    files_to_validate = chain(premis_valid, mets_valid, mods_valid)
    all_valid = True
    for is_valid, file_path in files_to_validate:
        if not is_valid:
            all_valid = False
            print(f"Failed XSD validation: {file_path}")

    return all_valid


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python validate_xsd.py PATH")
        exit(1)

    path = Path(sys.argv[1])
    is_valid = validate_xsd(path)
    if not is_valid:
        print("Some files did not pass XSD validation.")
        exit(1)

    print("XML files validated against XSD.")
    exit(0)
