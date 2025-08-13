# Changelog

## [0.3.0](https://github.com/minceheid/openeo/compare/v0.2.3...v0.3.0) (2025-08-13)


### Features

* improved deploy script ([c1fb062](https://github.com/minceheid/openeo/commit/c1fb0627879bf76850a8bd8fba29f1d125f3769e))
* Improved handling of serial overruns ([#31](https://github.com/minceheid/openeo/issues/31)) ([6164f46](https://github.com/minceheid/openeo/commit/6164f4612053486414c419cdbcd8b6534933a8a7))


### Bug Fixes

* abstracted charger response decoding into the charger class ([#41](https://github.com/minceheid/openeo/issues/41)) ([16afab9](https://github.com/minceheid/openeo/commit/16afab910490ad15c8bf1a98de1cba0bc54d7cec))
* add python3-psutil to deploy.bash ([415a195](https://github.com/minceheid/openeo/commit/415a1958cdf035fe8d6696960231735dd67e3bea))
* crontab entry broken in deploy.bash ([68efd5c](https://github.com/minceheid/openeo/commit/68efd5cb30cbeab77ff54fe98157f320aa5c8226))
* deploy ([fb28e16](https://github.com/minceheid/openeo/commit/fb28e1654abd83daa522ce7f02abe5e8bc1cd850))
* deploy ([ce413bb](https://github.com/minceheid/openeo/commit/ce413bb20d0c7e4fe658db23ccb88b0f5f6c29b6))
* disable portal - I think we have a race condition that is knocking out wifi ([c9f73e4](https://github.com/minceheid/openeo/commit/c9f73e4bad5cebc4ea03232813bc586bea212cf4))
* make curl quiet in deploy.bash ([5e3ce53](https://github.com/minceheid/openeo/commit/5e3ce53cb33b718bd20ae1b59a8873ce3c9d99e7))
* merge errors ([71d3c28](https://github.com/minceheid/openeo/commit/71d3c2809fa1b243c5d421789749fdc62bfa91d5))

## [0.2.3](https://github.com/minceheid/openeo/compare/v0.2.2...v0.2.3) (2025-07-24)


### Bug Fixes

* Correct publishing when Release Please runs ([#29](https://github.com/minceheid/openeo/issues/29)) ([0c59593](https://github.com/minceheid/openeo/commit/0c595930298de40d6aaeaa7dd42ab1fe5c78eaf2))

## [0.2.2](https://github.com/minceheid/openeo/compare/v0.2.1...v0.2.2) (2025-07-23)


### Bug Fixes

* ensure that all duty cycle values are uppercase ([f97666e](https://github.com/minceheid/openeo/commit/f97666eb667d3ae8bcd45ceaf7a371d3d4922c7b))
* ensure that all duty cycle values are uppercase ([8b9f65b](https://github.com/minceheid/openeo/commit/8b9f65bcf8227c83c20364837c702bf56b6cdf53))
* make charging more permissive ([f4bca82](https://github.com/minceheid/openeo/commit/f4bca8214ff6b3c56d8d1a922d1c5f7f31c10bc0))
* make charging more permissive ([3a6047e](https://github.com/minceheid/openeo/commit/3a6047e4c5b2e4842970cee74caa952d1b47ac77))

## 0.2.0 (2025-07-20)


### Features

* Add .gitattributes and apply to existing files ([062ef87](https://github.com/minceheid/openeo/commit/062ef87e925a3fd9b0d380dee9f6b818f7268d85))
* Add publishing mechanism ([41d4a63](https://github.com/minceheid/openeo/commit/41d4a6347dcaaacb347e7ca932fd9e6bf8f38770))


### Bug Fixes

* Update release please ([1be6f8b](https://github.com/minceheid/openeo/commit/1be6f8b366f735efb86f74ae8dea9f5b55cf2675))
