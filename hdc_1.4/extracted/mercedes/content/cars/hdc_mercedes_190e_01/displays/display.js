/// <reference path="../../common_assets/displays/js/BaseCarDisplay.js" />
/// <reference path="../../common_assets/displays/js/displays.js" />
/// <reference path="../../../../uiresources/src/js/ksUI.js" />

const eDisplayPages = {
    on: "on",
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

    ...window.getNewDisplay(eDisplayPages.on, 100),

    init: () => {
        console.log("CarDisplay.init: ks_mercedes_190e_evo_ii");
            },

    process: (cardata) => {

        if (!COMMON.process(cardata)) {
            return;
        }

        CarDisplay.displayIndex(CarDisplay.getCurrentIndex());

    }
}

engine.whenReady.then(
    () => {
        document.body.classList.add("loaded");
    }
);