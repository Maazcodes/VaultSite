function formatNumber(number, decimal) {
    decimal = decimal || 0;
    var decimalDigits = parseInt((number % 1) * (10 ** decimal));
    var i = 0;
    var str = [];
    for (let c of parseInt(number).toString().split("").reverse()) {
        if (i > 0 && i % 3 === 0) str.push(",");
        str.push(c);
        i++;
    }
    return str.reverse().join("") + (decimalDigits > 0 ? "." + decimalDigits : "");
}

function formatBytes(bytes, decimal) {
    var byteUnits = ["B", "KB", "MB", "GB", "TB"];
    var i = 0;
    while (bytes > 1024) {
        bytes = bytes / 1024;
        i++;
    }
    return formatNumber(bytes, decimal || 2) + " " + byteUnits[i];
}