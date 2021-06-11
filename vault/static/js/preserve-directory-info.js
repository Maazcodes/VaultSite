shasumsGlobal = {};

window.onload = function () {
    document.querySelector("#id_dir_field").addEventListener("change", function() {
        files = document.querySelector("#id_dir_field").files;
        let directories = {};
        let promises = [];
        shasumsGlobal = {};
        for (var file of files) {
            directories[file.name] = file.webkitRelativePath;
            promises.push(hashFile(file));
        };
        directories = JSON.stringify(directories);
        document.querySelector("#id_directories").value = directories;
        Promise.allSettled(promises).then(() => {
            shasums = JSON.stringify(shasumsGlobal);
            shasumsGlobal = {};
            document.querySelector("#id_shasums").value = shasums;
        });
    });

    document.querySelector("#id_file_field").addEventListener("change", function() {
        files = document.querySelector("#id_file_field").files;
        let directories = {};
        let promises = [];
        shasumsGlobal = {};
        for (var file of files) {
            directories[file.name] = file.name;
            promises.push(hashFile(file));
        };
        directories = JSON.stringify(directories);
        document.querySelector("#id_directories").value = directories;
        Promise.allSettled(promises).then(() => {
            shasums = JSON.stringify(shasumsGlobal);
            shasumsGlobal = {};
            document.querySelector("#id_shasums").value = shasums;
        });
    });

    document.querySelector("#id_collection").addEventListener("change", function() {
        let e = document.querySelector("#id_collection");
        let collname = e.options[e.selectedIndex].text;
        document.querySelector("#id_collname").value = collname;
    });
}

function bytesToHexString(bytes) {
    if (!bytes)
        return null;
    bytes = new Uint8Array(bytes);
    let hexBytes = [];
    for (let i = 0; i < bytes.length; ++i) {
        let byteString = bytes[i].toString(16);
        if (byteString.length < 2)
            byteString = "0" + byteString;
        hexBytes.push(byteString);
    }
    return hexBytes.join("");
}

//
// :FIXME: Fails on very large files.
// Unfortunately, old non-native hashing methods only work reliably for md5.
//
// Size will have to serve for now. Sigh.
//
async function hashFile(file) {
    let buffer = await file.arrayBuffer();
    return crypto.subtle.digest("SHA-256", buffer).then(function (hash) {
      shasumsGlobal[file.name] = bytesToHexString(hash);
    });
}

