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

    //const form = document.querySelector('form')
    //    form.addEventListener('submit', event => {
    //    // submit event detected
    //    event.preventDefault();
    //        XHRuploadFiles(event);
    //})


    async function XHRuploadFiles (evt) {
        start = performance.now();
        //let files = evt.target.files; // FileList object
     
        let files = document.querySelector("#id_file_field").files;

        for (let i = 0, f; f = files[i]; i++) {
    
            let data = new FormData();
    
            data.append('file', files[i]);
    
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
                console.log('Code: ' + xhr.status + ' Wire time: ' + runtime + 'ms');
                console.log(xhr.response);
            };
    
            xhr.send(data);
        };
    }

}

