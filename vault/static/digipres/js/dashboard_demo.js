Chart.defaults.global.defaultFontFamily = 'Nunito', '-apple-system,system-ui,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif';
Chart.defaults.global.defaultFontColor = '#858796';

chartalign.register("#worldmap", function (width, height) {
    return $("<div style=\"position: relative; width: " + width + "px; height: " + height + "px;\"></div>");
}, function ($el) {
    var bombMap = new Datamap({
        element: $el.get(0),
        scope: 'world',
        geographyConfig: {
            popupOnHover: false,
            highlightOnHover: false
        },
        fills: {
            'countries': '#2a282c',
            'regions': '#2991cc',
            defaultFill: '#e3e7e8'
        },
        data: {
            'USA': {fillKey: 'countries'},
            'NLD': {fillKey: 'countries'}
        }
    });

    var bombs = [{
        name: 'us-west-1',
        location: '300 Funston',
        radius: 10,
        country: 'USA',
        fillKey: 'regions',
        latitude: 37.782523,
        longitude: -122.471612
    }, {
        name: 'us-west-2',
        location: '2512 Florida',
        radius: 10,
        country: 'USA',
        fillKey: 'regions',
        latitude: 37.9292582,
        longitude: -122.4159501
    }, {
        name: 'eu-west-1',
        location: 'Amsterdam',
        radius: 10,
        country: 'NL (Europe)',
        fillKey: 'regions',
        latitude: 52.3546449,
        longitude: 4.8339212
    }, {
        name: 'ca-east-1',
        location: 'IAC',
        radius: 10,
        country: 'Canada',
        fillKey: 'regions',
        latitude: 45.4200567,
        longitude: -75.8479716
    }];

    bombMap.bubbles(bombs, {
        popupTemplate: function (geo, data) {
            return ['<div class="hoverinfo">' +  data.name,
                '<br/>Location: ' +  data.location + '',
                '<br/>Country: ' +  data.country + '',
                '</div>'].join('');
        }
    });

    return bombMap;
});

chartalign.register("#temporal-scans-chart", function (width, height) {
    return $("<canvas style=\"margin-top: -30px;\"></canvas>").attr("width", width).attr("height", height);
}, function ($el) {
    function number_format(number, decimals, dec_point, thousands_sep) {
        // *     example: number_format(1234.56, 2, ',', ' ');
        // *     return: '1 234,56'
        number = (number + '').replace(',', '').replace(' ', '');
        var n = !isFinite(+number) ? 0 : +number,
            prec = !isFinite(+decimals) ? 0 : Math.abs(decimals),
            sep = (typeof thousands_sep === 'undefined') ? ',' : thousands_sep,
            dec = (typeof dec_point === 'undefined') ? '.' : dec_point,
            s = '',
            toFixedFix = function(n, prec) {
                var k = Math.pow(10, prec);
                return '' + Math.round(n * k) / k;
            };
        // Fix for IE parseFloat(0.55).toFixed(0) = 0;
        s = (prec ? toFixedFix(n, prec) : '' + Math.round(n)).split('.');
        if (s[0].length > 3) {
            s[0] = s[0].replace(/\B(?=(?:\d{3})+(?!\d))/g, sep);
        }
        if ((s[1] || '').length < prec) {
            s[1] = s[1] || '';
            s[1] += new Array(prec - s[1].length + 1).join('0');
        }
        return s.join(dec);
    }

    return new Chart($el.get(0).getContext("2d"), {
        type: "line",
        data: {
            labels: ["Jul'20", "Aug'20", "Sep'20", "Oct'20", "Nov'20", "Dec'20", "Jan'20", "Feb'20", "Mar'20", "Apr'20", "May'20", "Jun'20"],
            datasets: [{
                label: "Files",
                cubicInterpolationMode: "default",
                lineTension: 0.3,
                backgroundColor: "#2991cc",
                borderColor: "#2480b4",
                pointRadius: 0,
                pointBackgroundColor: "#2991cc",
                pointBorderColor: "#2991cc",
                pointHoverRadius: 3,
                pointHoverBackgroundColor: "#2991cc",
                pointHoverBorderColor: "#2991cc",
                pointHitRadius: 10,
                pointBorderWidth: 2,
                data: [0, 3000, 2000, 4500, 4000, 3500, 4500, 7000, 6000, 9696, 9000, 8000]
            }]
        },
        options: {
            title: {
                display: true,
                text: 'Files Evolution per Check'
            },
            maintainAspectRatio: false,
            scales: {
                xAxes: [{
                    time: {
                        unit: 'date'
                    },
                    gridLines: {
                        display: true,
                        drawBorder: false
                    },
                    ticks: {
                        maxTicksLimit: 7
                    }
                }],
                yAxes: [{
                    scaleLabel: {
                        display: false,
                        labelString: "Files"
                    },
                    ticks: {
                        maxTicksLimit: 5,
                        padding: 10,
                        // Include a dollar sign in the ticks
                        callback: function(value, index, values) {
                            return number_format(value);
                        }
                    },
                    gridLines: {
                        color: "rgb(234, 236, 244)",
                        zeroLineColor: "rgb(234, 236, 244)",
                        drawBorder: false,
                        borderDash: [2],
                        zeroLineBorderDash: [2]
                    }
                }]
            },
            legend: {
                display: false
            },
            tooltips: {
                backgroundColor: "rgb(255,255,255)",
                bodyFontColor: "#858796",
                titleMarginBottom: 10,
                titleFontColor: '#6e707e',
                titleFontSize: 14,
                borderColor: '#dddfeb',
                borderWidth: 1,
                xPadding: 15,
                yPadding: 15,
                displayColors: false,
                intersect: false,
                mode: 'index',
                caretPadding: 10,
                callbacks: {
                    label: function(tooltipItem, chart) {
                        var datasetLabel = chart.datasets[tooltipItem.datasetIndex].label || '';
                        return datasetLabel + ': ' + number_format(tooltipItem.yLabel);
                    }
                }
            }
        }
    });
}, function (chart) {
    chart.destroy();
});

chartalign.register("#worldmap-histogram", function (width, height) {
    return $("<canvas></canvas>").attr("width", width).attr("height", height);
}, function ($el) {
    return new Chart($el.get(0), {
        type: 'bar',
        data: {
            labels: ["us-west-1", "us-west-2", "ca-east-1", "eu-west-1"],
            datasets: [
                {
                    label: "Files",
                    backgroundColor: ["#3e95cd", "#8e5ea2","#3cba9f","#e8c3b9","#c45850"],
                    data: [2478,5267,734,784,433]
                }
            ]
        },
        options: {
            legend: { display: false },
            title: {
                display: true,
                text: 'Files per Region'
            }
        }
    });
}, function (chart) {
    chart.destroy()
});

chartalign.register("#collections-chart", function (width, height) {
    return $("<canvas></canvas>").attr("width", width).attr("height", height);
}, function ($el) {
    return new Chart($el.get(0), {
        type: 'doughnut',
        data: {
            labels: ["Collection 1", "Collection 2", "Collection 3", "Collection 4", "Collection 5", "Collection 6", "Collection 7", "Collection 8", "Collection 9"],
            datasets: [
                {
                    label: "Collections",
                    backgroundColor: ["#306ccd", "#a27698","#21ba60","#e8e6c5","#c45850", "#3e95cd", "#8e5ea2","#3cba9f","#e8c3b9","#c45850"],
                    data: [1000, 2267, 484, 433, 734, 1200, 1278, 2000, 300]
                }
            ]
        },
        options: {
            legend: { display: false },
            title: {
                display: true,
                text: 'Collections Distribution (%)'
            }
        }
    });
}, function (chart) {
    chart.destroy();
});

chartalign.register("#filetypes-chart", function (width, height) {
    return $("<canvas></canvas>").attr("width", width).attr("height", height);
}, function ($el) {
    return new Chart($el.get(0), {
        type: 'doughnut',
        data: {
            labels: ["GZIP", "WARC", "TXT", "ARC", "PDF"],
            datasets: [
                {
                    label: "File types",
                    backgroundColor: ["#3e95cd", "#8e5ea2","#3cba9f","#e8c3b9","#c45850"],
                    data: [2478,5267,734,784,433]
                }
            ]
        },
        options: {
            title: {
                display: true,
                text: 'File Types Distribution (%)'
            }
        }
    });
}, function (chart) {
    chart.destroy();
});