/// <reference path="../../common_assets/displays/js/BaseCarDisplay.js" />
/// <reference path="../../common_assets/displays/js/displays.js" />
/// <reference path="../../../../uiresources/src/js/ksUI.js" />

const eDisplayPages = {
    clock: "clock",
    fuel: "fuel",
    ambient: "ambient",
    startup: "startup"
};

const eDisplayModes = {
    mode1: "mode1",
    mode2: "mode2",
    startup: "startup"
};


/** 
@type { import('../../common_assets/displays/js/BaseCarDisplay.js').default } BaseCarDisplay
*/
const CarDisplay = {

    ...window.getNewDisplay(eDisplayPages.on, 0),

    init: () => {
        console.log("CarDisplay.init: ks_bmw_m3_e46_csl");
    },

    process: (cardata) => {

        if (!COMMON.process(cardata)) {
            return;
        }

        CarDisplay.changeMode(cardata.low_frequency.electronics.active_performance_mode);
        CarDisplay.displayIndex(CarDisplay.getCurrentIndex());

    }
}

engine.whenReady.then(
    () => {
        document.body.classList.add("loaded");
    }
);