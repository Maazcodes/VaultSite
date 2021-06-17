window.onload = function () {
    document.querySelector("#id_dir_field").addEventListener("change", function() {
        document.querySelector("#id_file_field").disabled = true;
        let directories = [];
        let files = document.querySelector("#id_dir_field").files;
        for (var file of files) {
            directories.push(file.webkitRelativePath);
        }
        document.querySelector("#id_directories").value = directories.toString();
    });


    document.querySelector("#id_file_field").addEventListener("change", function() {
        document.querySelector("#id_dir_field").disabled = true;
        let directories = [];
        let files = document.querySelector("#id_file_field").files;
        for (var file of files) {
            directories.push(file.name);
        }
        document.querySelector("#id_directories").value = directories.toString();
    });


    const form = document.querySelector('form')
    form.addEventListener('submit', event => {
        event.preventDefault();
        XHRuploadFiles(form);
    })

    async function XHRuploadFiles (form) {
        let total_size = 0;
        let num_files  = 0;
        start = performance.now();
        
        let collection = document.querySelector("#id_collection").value;
        
        let files = [];
        if (document.querySelector("#id_file_field").disabled == true) {
            files = document.querySelector("#id_dir_field").files;
        } else {
            files = document.querySelector("#id_file_field").files;
        };

        let data = new FormData(form);
        for (let i = 0, f; f = files[i]; i++) {
    
            total_size = total_size + f.size;
            num_files  = num_files + 1;
            data.append('file', f);
         };

            let xhr = new XMLHttpRequest();
            xhr.open('POST', '/vault/deposit/web', true);
    
            xhr.onerror = function () {
                console.error('<b>Request Failed: Network Error.</b>');
            };
    
            xhr.onabort = function () {
                console.error('<b>Request Aborted.</b>');
            };
    
            xhr.upload.onprogress = function(e) {
                if (e.lengthComputable) {
                    let progress = Math.round((e.loaded / e.total)*100);
                    document.querySelector('#progress_bar').value = progress;
                };
            };
    
            xhr.onloadend = function() {
                let end = performance.now();
                let runtime = end - start;
                start = end;
                let msg = "";
                msg += 'Return Code: ' + xhr.status;
                msg += ' Number of files transferred: ' + num_files;
                msg += ' Total Bytes: ' + total_size;
                msg += ' Runtime: ' + runtime + 'ms';
                document.querySelector('#stats').innerHTML += '<pre>' + msg + '</pre>'
                console.log(msg);
                console.log(xhr.response);
                resetForm();
            };
    
            xhr.send(data);
    }
    
    function resetForm() {
        form.reset()
        document.querySelector("#id_file_field").disabled = false;
        document.querySelector("#id_dir_field").disabled = false;
        document.querySelector('#progress_bar').value = 0;
    }
}

