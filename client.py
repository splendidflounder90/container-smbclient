import os
import json
import base64
import requests
from urllib.parse import urlparse
from smbclient import register_session, mkdir, rmdir, scandir, open_file, remove

SUPPORTED_ACTIONS = {
    "directory": ["create", "read", "delete"],
    "file": ["create", "read", "delete"]
}

def validate_environment_variables(required_vars:list):    
    for var in required_vars:
        if not os.getenv(var):
            raise ValueError(f"Missing environment variable: {var}")
    return True

def is_base64(s):
    try:
        decoded = base64.b64decode(s,validate=True)
        encoded = base64.b64encode(decoded).decode('utf-8')
        return encoded == s
    except Exception:
        return False
    
def is_url(url):
    parsed_url = urlparse(url)
    return bool(parsed_url.scheme and parsed_url.netloc)

def main():
    # validate core connection parameters
    if validate_environment_variables(["ACTION", "SMB_SERVER", "DIRECTORY"]):
        
        server = str(os.getenv("SMB_SERVER")).rstrip("\\")
        directory = str(os.getenv("DIRECTORY")).strip("\\")
        username = os.getenv("SMB_USERNAME")
        password = os.getenv("SMB_PASSWORD")
        file_name = os.getenv("FILE_NAME")
                
        if file_name:
            target = "file"
            # build full unc path including file_name
            unc_path = r"\\{}\{}\{}".format(server, directory, file_name)
        else:
            target = "directory"
            unc_path = r"\\{}\{}".format(server, directory)

        
        # validate required parameters per action
        action=str(os.getenv("ACTION")).lower()
        
        if not action in SUPPORTED_ACTIONS[target]:
            raise ValueError(f"{action} is not supported")

        if username and password:
            # setup authenticated connection
            register_session(server=server, username=username, password=password)
        else:
            # setup unauthenticated connection
            register_session(server=server, username="Guest", password="ignored")
        
        if target == "file":
            if action == "create":
                if validate_environment_variables(["FILE_CONTENTS"]):
                    file_contents = str(os.getenv("FILE_CONTENTS"))
                    if is_url(file_contents):
                        url = file_contents
                        # download file from url and save to directory
                        with requests.get(url, stream=True) as r:
                            r.raise_for_status()
                            with open_file(unc_path,mode="wb") as f:
                                for chunk in r.iter_content(chunk_size=8192):
                                    f.write(chunk)
                        print(json.dumps({"output":"File created."}))
                    elif is_base64(file_contents):
                        decoded=base64.b64decode(file_contents)
                        with open_file(unc_path,mode="wb") as f:                        
                            f.write(decoded)
                        print(json.dumps({"output":"File created."}))
                    else:
                        raise ValueError("Invalid file contents format. Must be base64 encoded or a valid URL.")
            elif action == "read":
                with open_file(unc_path,mode="rb") as f:
                    f_bytes = f.read()
                b64_encoded = base64.b64encode(f_bytes)
                print(json.dumps({"output":b64_encoded.decode()}))                
            elif action == "delete":
                remove(unc_path)
                print(json.dumps({"output":"File deleted."}))
        
        elif target == "directory":
            if action == "create":
                mkdir(unc_path)
                print(json.dumps({"output":"Directory created."}))            
            elif action == "read":
                # list directory contents            
                contents = []            
                for file_info in scandir(unc_path):
                    obj = {"name":file_info.name}
                    if file_info.is_file():                    
                        file_stat = file_info.stat()
                        obj.update({"type":"file","size":file_stat.st_size})
                        
                    elif file_info.is_dir():
                        obj.update({"type":"directory"})                                   
                    else:
                        obj.update({"type":"symlink"})                    
                    
                    contents.append(obj)

                print(json.dumps({"output":contents}))
            elif action == "delete":            
                rmdir(unc_path)
                print(json.dumps({"output":"Directory deleted."}))

if __name__ == "__main__":
    main()
