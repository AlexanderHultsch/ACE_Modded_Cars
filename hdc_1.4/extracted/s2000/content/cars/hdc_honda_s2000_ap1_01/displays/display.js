/// <reference path="../../common_assets/displays/js/BaseCarDisplay.js" />
/// <reference path="../../common_assets/displays/js/displays.js" />
/// <reference path="../../../../uiresources/src/js/ksUI.js" />

const eDisplayPages = {
    page1: "page1",
    startup: "startup"
};

const eDisplayModes = {
    mode1: "mode1",
    startup: "startup"
};

const rpmTable = [
    [null, 0, 1],
    [0, 390, -27],
    [900, 492, 146],
    [1000, 512, 172],
    [2000, 646, 396],
    [3000, 757, 582],
    [4000, 857, 742],
    [5000, 943, 888],
    [6000, 1047, 1047],
    [7000, 1158, 1244],
    [8000, 1320, 1505],
    [8500, 1432, 1692],
    [8800, 1517, 1830],
    [9300, 1523, 1836]
];

const tempTable = [
    [null, 0, 1],
    [0, 309, 320],
    [60, 343, 354],
    [65, 343, 354],
    [70, 377, 388],
    [75, 377, 388],
    [80, 411, 422],
    [85, 443, 454],
    [90, 443, 454],
    [95, 477, 488],
    [100, 509, 520],
    [105, 542, 553],
    [110, 548, 559],
    [150, 548, 559],
]

const fuelTable = [
    [null, 0, 1],
    [0, 1510, 1521],
    [3, 1510, 1521],
    [5, 1530, 1541],
    [7.5, 1545, 1556],
    [10, 1558, 1569],
    [25, 1636, 1647],
    [27.5, 1649, 1660],
    [30, 1649, 1660],
    [35, 1675, 1686],
    [40, 1701, 1712],
    [45, 1727, 1738],
    [50, 1753, 1764],
    [100, 1754, 1765],
]

/** 
@type { import('../../common_assets/displays/js/BaseCarDisplay.js').default } BaseCarDisplay
*/
const CarDisplay = {

    labelSpeed: null,
    delayed125: false,
    delayed250: false,

    /** @type HTMLDivElement */
    rpmMask: null,

    /** @type HTMLDivElement */
    tempMask: null,

    /** @type HTMLDivElement */
    fuelMask: null,

    ...window.getNewDisplay(eDisplayPages.page2, 1000),

    init: () => {
        console.log("CarDisplay.init: Honda S2000 AP1");

        CarDisplay.labelSpeed = $.q("#speed");

        CarDisplay.rpmMask = $.q("#rpm");
        CarDisplay.tempMask = $.q("#temperature");
        CarDisplay.fuelMask = $.q("#fuel");
    },

    lastUpdateTime: 0,

    process: (cardata) => {

        if (!COMMON.process(cardata)) {
            return;
        }

        const delta = Date.now() - CarDisplay.lastUpdateTime;

        CarDisplay.delayed250 = delta >= 250;
        CarDisplay.delayed125 = delta >= 125;

        if (CarDisplay.delayed250) {
            CarDisplay.lastUpdateTime = Date.now();
            CarDisplay.labelSpeed.textContent = cardata.display_speed_kmh;
            CarDisplay.fuel(cardata.fuel_liter_current_quantity);
            CarDisplay.temperature(cardata.water_temperature_c);
        }

        CarDisplay.rpm(cardata.rpm);

    },

    rpm: (value) => {
        const maskpoints = CarDisplay.convert.tableToClipPath(100 * Math.round(value / 100), rpmTable, true);
        const strClipPath = `clip-path: polygon(-27px 62px, 388px 356px, ${Math.round(maskpoints[0])}px 356px, ${Math.round(maskpoints[1])}px 62px);`;
        CarDisplay.rpmMask.setAttribute("style", strClipPath);
    },

    temperature: (value) => {
        const maskpoints = CarDisplay.convert.tableToClipPath(5 * Math.ceil(value / 5), tempTable, true);
        const strClipPath = `clip-path: polygon(319px 430px, 308px 462px, ${Math.round(maskpoints[0])}px 462px, ${Math.round(maskpoints[1])}px 430px);`;
        CarDisplay.tempMask.setAttribute("style", strClipPath);
    },

    fuel: (value) => {
        const maskpoints = CarDisplay.convert.tableToClipPath(2.5 * Math.floor(value / 2.5), fuelTable, true);
        const strClipPath = `clip-path: polygon(1514px 430px, 1503px 462px, ${Math.round(maskpoints[0])}px 462px, ${Math.round(maskpoints[1])}px 430px);`;
        CarDisplay.fuelMask.setAttribute("style", strClipPath);
    },
}

engine.whenReady.then(
    () => {
        document.body.classList.add("loaded");
    }
);