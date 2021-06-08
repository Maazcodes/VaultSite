window.onload = function () {
    document.querySelector("#id_dir_field").addEventListener("change", function() {
        files = document.querySelector("#id_dir_field").files;
        var directories = {};
        for (var file of files) {
            directories[file.name] = file.webkitRelativePath;
        }
    directories = JSON.stringify(directories);
    document.querySelector("#id_directories").value = directories
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

function reportHashResult (theFile) {
    file_information = JSON.stringify({
        'name': theFile.name,
        'lastModified': theFile.lastModified,
        'lastModifiedDate': theFile.lastModifiedDate,
        'webkitRelativePath': theFile.webkitRelativePath,
        'size': theFile.size,
        'file_type': theFile.type,
        'md5sum': '_._MD5SUM_._:',
        'sha1sum': bytesToHexString(theFile.SHA1),
        'sha256sum': bytesToHexString(theFile.SHA256),
        'hash_time_ms': theFile.run_time,
        'date': Date.now()
    });
    document.querySelector('#checksum_textarea').value += file_information + ',\n';
    document.querySelector('#hashtime_textarea').value   += theFile.size + " bytes in: " + theFile.run_time + " ms\n";
}

async function handleFileSelect(evt) {
    let files = evt.target.files; // FileList object

    // Loop through the FileList and generate shasum
    for (let i = 0, f; f = files[i]; i++) {
        
        let reader = new FileReader();
        // Closure to capture the file information.
        reader.onload = (function (theFile) {
            return function (e) {
                let start_time = performance.now();
                window.crypto.subtle.digest(
                        { name: 'SHA-1'}, e.target.result
                ).then(function (hash) {
                    theFile.SHA1 = hash;
                })
                .catch(function (err) {
                    console.error(err);
                });
                window.crypto.subtle.digest(
                        { name: 'SHA-256'}, e.target.result
                ).then(function (hash) {
                    run_time = (performance.now() - start_time);
                    theFile.SHA256 = hash;
                    theFile.run_time = run_time;
                    reportHashResult(theFile);
                })
                .catch(function (err) {
                    console.error(err);
                });
            };
        })(f);
        // Read in the file
        reader.readAsArrayBuffer(f);
    };
}

//window.onload = function () {
//  document.querySelector('#hash_file').addEventListener('change', handleFileSelect, false);
//  document.querySelector('#hash_directory').addEventListener('change', handleFileSelect, false);
//};
