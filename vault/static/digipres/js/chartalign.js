var chartalign = (function () {
    var chartContainerClass = "chart-container";

    var registeredCharts = {};
    var initialized = false;

    function init() {
        redraw();
        initialized = true;
    }

    function register(selector, create, init, destroy) {
        unregister(selector);
        var chart = {
            selector: selector,
            create: create,
            init: init,
            destroy: destroy
        };
        registeredCharts[selector] = chart;
        if (initialized) redrawChart(chart);
    }

    function redrawChart(chart) {
        if (chart.obj && chart.destroy) chart.destroy(chart.obj);
        if (chart.$container) chart.$container.remove();
        chart.$container = $("<div>").addClass(chartContainerClass).appendTo($(chart.selector));
        var width = chart.$container.width();
        var height = chart.$container.height();
        var $el = chart.create(width, height);
        chart.$container.append($el);
        chart.obj = chart.init($el);
    }

    function redraw() {
        for (let chart of Object.values(registeredCharts)) redrawChart(chart);
    }

    function unregister(selector) {
        var chart = registeredCharts[selector];
        if (chart) {
            if (chart.destroy) chart.destroy(chart.obj);
            delete registeredCharts[selector];
        }
    }

    function unregisterAll() {
        for (let chart of Object.values(registeredCharts)) if (chart.destroy) chart.destroy();
        registeredCharts = {};
    }

    return {
        register: register,
        unregister: unregister,
        unregisterAll: unregisterAll,
        redraw: redraw,
        init: init
    };
})();

$(function () {
    $(window).resize(function () {
        chartalign.redraw();
    });

    chartalign.init();
});