from typing import cast
from pathlib import Path
from hashlib import md5
import xml.etree.ElementTree as ET


class ValidationError(Exception): ...


class NamespaceMeta(type):
    __ns__: str

    def __getattr__(cls, item: str) -> str:
        return "{" + cls.__ns__ + "}" + item


class Namespace(metaclass=NamespaceMeta):
    def __new__(cls, ns: str):
        class_name = f"Namespace_{abs(hash(ns))}"
        return NamespaceMeta(class_name, (object,), {"__ns__": ns})


mets = Namespace(ns="http://www.loc.gov/METS/")
xlink = Namespace(ns="http://www.w3.org/1999/xlink")
xsi = Namespace(ns="http://www.w3.org/2001/XMLSchema-instance")
premis = Namespace(ns="http://www.loc.gov/premis/v3")


def validate_checksums_and_sizes(sip_path: Path) -> bool:
    mets_paths = sip_path.rglob("METS.xml")
    premis_paths = sip_path.rglob("premis.xml")

    mets_valid = all(validate_mets(path) for path in mets_paths)
    premis_valid = all(validate_premis(path) for path in premis_paths)

    return mets_valid and premis_valid


def validate_premis(premis_path: Path) -> bool:
    root = parse_xml(premis_path)

    xpath = f"{premis.object}[@{xsi.type}='{premis.file}']"
    premis_files = recursive_findall(root, xpath)

    return all(validate_premis_file(premis_path, file) for file in premis_files)


def validate_premis_file(premis_path: Path, premis_file: ET.Element) -> bool:
    original_name = premis_file.find(premis.originalName)
    if original_name is None or original_name.text is None:
        raise ValidationError(f"Missing original name in premis: {premis_path}")

    checksum_xpath = (
        premis.objectCharacteristics + "/" + premis.fixity + "/" + premis.messageDigest
    )
    size_xpath = premis.objectCharacteristics + "/" + premis.size
    size = next(iter(premis_file.findall(size_xpath)), None)
    if size is None or size.text is None:
        raise ValidationError(f"Missing premis:size: {premis_path}")

    checksum = next(iter(premis_file.findall(checksum_xpath)), None)
    if checksum is None or checksum.text is None:
        raise ValidationError(f"Missing premis:size: {premis_path}")

    checksum = checksum.text
    size = int(size.text)
    preservation_dir = premis_path.parent
    metadata_dir = preservation_dir.parent
    representation_dir = metadata_dir.parent
    href = representation_dir / "data" / original_name.text
    with open(href, "br") as file:
        calculated_checksum = md5(file.read()).hexdigest()
    calculated_size = href.stat().st_size

    if calculated_checksum != checksum:
        print(f"Incorrect checksum for file: {href}")
        return False

    if calculated_size != size:
        print(f"Incorrect size for file: {href}")
        return False

    return True


def validate_mets(mets_path: Path) -> bool:
    root = ET.parse(mets_path).getroot()

    mdrefs = recursive_findall(root, mets.mdRef)
    files = recursive_findall(root, mets.file)
    mdrefs_valid = all(validate_mets_mdref(mets_path, mdref) for mdref in mdrefs)
    files_valid = all(validate_mets_file(mets_path, file) for file in files)

    return mdrefs_valid and files_valid


def validate_mets_mdref(mets_path: Path, element: ET.Element) -> bool:
    href = element.attrib.get(xlink.href)
    size = element.attrib.get("SIZE")
    checksum = element.attrib.get("CHECKSUM")
    checksum_type = element.attrib.get("CHECKSUMTYPE")

    if href is None or size is None or checksum is None or checksum_type != "MD5":
        raise ValidationError(
            "Could not find xlink:href, SIZE, CHECKSUM or CHECKSUMTYPE"
        )

    size = int(size)
    href = mets_path.parent / href
    with open(href, "br") as file:
        calculated_checksum = md5(file.read()).hexdigest()
    calculated_size = href.stat().st_size

    if calculated_checksum != checksum:
        print(f"Incorrect checksum for file: {href}")
        return False

    if calculated_size != size:
        print(f"Incorrect size for file: {href}")
        return False

    return True


def validate_mets_file(mets_path: Path, element: ET.Element) -> bool:
    size = element.attrib.get("SIZE")
    checksum = element.attrib.get("CHECKSUM")
    checksum_type = element.attrib.get("CHECKSUMTYPE")

    if size is None or checksum is None or checksum_type != "MD5":
        raise ValidationError(
            "Could not find xlink:href, SIZE, CHECKSUM or CHECKSUMTYPE"
        )

    flocat = element.find(mets.FLocat)
    if flocat is None:
        raise ValidationError("Could not find mets:Flocat")

    href = flocat.attrib.get(xlink.href)
    if href is None:
        raise ValidationError("Could not find xlink:href")

    size = int(size)
    href = mets_path.parent / href
    with open(href, "br") as file:
        calculated_checksum = md5(file.read()).hexdigest()
    calculated_size = href.stat().st_size

    if calculated_checksum != checksum:
        print(f"Incorrect checksum for file: {href}")
        return False

    if calculated_size != size:
        print(f"Incorrect size for file: {href}")
        return False

    return True


def recursive_findall(element: ET.Element, path: str) -> list[ET.Element]:
    result = element.findall(path)
    for child in element:
        result += recursive_findall(child, path)
    return result


def expand_qname_attributes(
    element: ET.Element, document_namespaces: dict[str, str]
) -> ET.Element:
    """
    Certain attributes may have a prefixed value e.g. xsi:type="schema:Episode".
    Expand the prefixed attribute value to its full qualified name e.g. "{https://schema.org/}Episode"
    """

    for k, v in element.attrib.items():
        if k == xsi.type:
            element.attrib[k] = expand_qname(v, document_namespaces)

    for child in element:
        _ = expand_qname_attributes(child, document_namespaces)

    return element


def parse_xml(source: Path) -> ET.Element:
    document_namespaces = get_document_namespaces(source)
    tree = ET.parse(source)
    expand_qname_attributes(tree.getroot(), document_namespaces)
    return tree.getroot()


def expand_qname(name: str, document_namespaces: dict[str, str]) -> str:
    """
    Expand a prefixed qualified name to its fully qualified name.
    E.g. "schema:Episode" is expanded to "{https://schema.org/}Episode"
    """

    if ":" not in name:
        return name

    splitted_qname = name.split(":", 1)
    prefix = splitted_qname[0]
    local = splitted_qname[1]
    prefix_iri = document_namespaces[prefix]

    return "{" + prefix_iri + "}" + local


def get_document_namespaces(source: Path) -> dict[str, str]:
    document_namespaces = [
        ns_tuple for _, ns_tuple in ET.iterparse(source, events=["start-ns"])
    ]
    return dict(cast(list[tuple[str, str]], document_namespaces))


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python validate_sip.py PATH")
        exit(1)

    path = Path(sys.argv[1])

    try:
        is_valid = validate_checksums_and_sizes(path)
    except Exception:
        print(f"Error while validating '{path}'")
        exit(1)

    if not is_valid:
        print(f"Invalid METS.xml or premis.xml found: {path}")
        exit(1)

    print(f"All METS.xml and premis.xml validated: {path}")
    exit(0)
