/* Native accessory display bootstrap, following the stock AE86 clock convention. */
const eDisplayPages = { chime: "chime", startup: "startup" };
const eDisplayModes = { mode1: "mode1", startup: "startup" };
const CarDisplay = {
    ...window.getNewDisplay(eDisplayPages.chime, 0, false),
    init: () => {},
    process: (cardata) => {
        // A missing native model must not make the off-switch throw.
        if (!cardata || !cardata.low_frequency ||
            !cardata.low_frequency.electronics || !cardata.low_frequency.instrumentation ||
            !cardata.low_frequency.electronics_max_limit || !cardata.low_frequency.flags) return false;
        return COMMON.process(cardata);
    }
};
engine.whenReady.then(() => { document.body.classList.add("loaded"); });
