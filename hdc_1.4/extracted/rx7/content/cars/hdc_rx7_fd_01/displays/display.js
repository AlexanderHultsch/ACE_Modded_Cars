/// <reference path="../../common_assets/displays/js/BaseCarDisplay.js" />
/// <reference path="../../common_assets/displays/js/displays.js" />
/// <reference path="../../../../uiresources/src/js/ksUI.js" />

const eDisplayPages = {
    normal: "normal",
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


    ...window.getNewDisplay(eDisplayPages.normal, 100),

    init: () => {
        console.log("CarDisplay.init: ks_mazda_rx7_fd");
    },

    process: (cardata) => {

        if (!COMMON.process(cardata)) {
            return;
        }

    }
}

engine.whenReady.then(
    () => {
        document.body.classList.add("loaded");
    }
);