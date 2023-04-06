from __future__ import annotations
import os
import sys
import json
import re

plugins = []

EXCLUDES = ['manifest.json', 'LICENSE', 'updater.py', '.gitignore', '.git']
files = filter(lambda name: name not in EXCLUDES and os.path.isdir(name), os.listdir())

MANIFEST_KEYS = {"version", "tag", "name", "description", "authors"}

def manifest_from_decorator(init: str) -> dict | None:
    with open(init, "r") as f:
        code = f.read()
    result = re.search('DecoratorPlugin\(["|\'](.+)["|\'],[ ]?["|\'](.+)["|\'],[ ]?["|\'](.+)["|\'],[ ]?(\[.+\])\)', code)
    if not result:
        print(f"{init} is not a DecoratorPlugin")
        return None
    try:
        tag = result.group(1)
        name = result.group(2)
        description = result.group(3)
        authors = result.group(4)
    except IndexError:
        print("Cannot extract all the necessary data from DecoratorPlugin")
        return None
    try:
        authors = json.loads(authors.replace("'", "\""))
    except json.decoder.JSONDecodeError:
        print(f"Cannot parse authors from {init}")
        return None
    return {
        "version": (1,0,0),
        "tag": tag,
        "name": name,
        "description": description,
        "authors": authors
    }

def manifest_from_class_plugin(init: str) -> dict | None:
    with open(init, "r") as f:
        code = f.read()
    result = re.search('super\(\)\.__init__\("(.+)",[ ]?"(.+)",[ ]?"(.+)",[ ]?(\[.+\])\)', code)
    if not result:
        print(f"{init} is not a Class Based Plugin")
        return None
    try:
        tag = result.group(1)
        name = result.group(2)
        description = result.group(3)
        authors = result.group(4)
    except IndexError:
        return None
    try:
        authors = json.loads(authors)
    except json.decoder.JSONDecodeError:
        return None
    return {
        "version": (1,0,0),
        "tag": tag,
        "name": name,
        "description": description,
        "authors": authors
    }

def read_manifest(path: str):
    with open(manifest, "r") as f:
            data = f.read()
    try: 
        return json.loads(data)
    except json.decoder.JSONDecodeError:
        return None

def test_manifest(data: dict | None):
    if not data:
        return False

    diff = set(data.keys()) - MANIFEST_KEYS
    if diff:
        return False

    # FIXME: check the declared value types

    return True
    


for path in files:
    print(f"Checking {path}")
    # Checking if __init__.py exists
    init = os.path.join(path, "__init__.py")
    init_exists = os.path.exists(init)
    
    # Checking if the plugin has a manifest.json
    manifest = os.path.join(path, "manifest.json")
    manifest_exists = os.path.exists(manifest)

    if not manifest_exists and init_exists:
        print("Missing plugin manifest. Trying to generate from __init__.py")
        print(f"Testing if {path} is a DecoratorPlugin")
        manifest_data = manifest_from_decorator(init)
        if not manifest_data:
            print(f"{path} is not a DecoratorPlugin, testing if it's a class based plugin")
            manifest_data = manifest_from_class_plugin(init)
        if manifest_data:
            print("Writing generated manifest")
            with open(manifest, "w") as f:
                f.write(json.dumps(manifest_data))
            manifest_exists = True
        else:
            print("Cannot generate a valid manifest from plugin")
    if manifest_exists:
        data = read_manifest(manifest)
        if not test_manifest(data):
            print(f"Invalid Manifest, ignoring {path}")
        else:
            print(f"Manifest is valid. Adding {path} to the repository")
            plugins.append(data)

with open("manifest.json", "r") as f:
    manifest = f.read()
    try:
        data = json.loads(manifest)
    except json.decoder.JSONDecodeError:
        print("Current repository has an invalid Manifest")
        sys.exit(-1)

if data:
    with open("manifest.json", "w") as f:
        data["plugins"] = plugins
        f.write(json.dumps(data, indent=4))
    

    
        
            
    
