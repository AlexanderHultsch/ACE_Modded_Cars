/// <reference path="../../common_assets/displays/js/BaseCarDisplay.js" />
/// <reference path="../../common_assets/displays/js/displays.js" />
/// <reference path="../../../../uiresources/src/js/ksUI.js" />

const eDisplayPages = {
    clock: "clock",
    startup: "startup"
};

const eDisplayModes = {
    mode1: "mode1",
    startup: "startup"
};


/** 
@type { import('../../common_assets/displays/js/BaseCarDisplay.js').default } BaseCarDisplay
*/
const CarDisplay = {

    clock: null,
    ambient: null,

    ...window.getNewDisplay(eDisplayPages.clock, 100),

    init: () => {
        console.log("CarDisplay.init: ks_toyota_ae86_sprinter_trueno");
        CarDisplay.clock = $.q("#clock");
    },

    process: (cardata) => {

        if (!COMMON.process(cardata)) {
            return;
        }

        CarDisplay.clock.textContent = CarDisplay.convert.timeOfDayToTime(cardata);
    }
}

engine.whenReady.then(
    () => {
        document.body.classList.add("loaded");
    }
);