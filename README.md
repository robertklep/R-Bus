# R-Bus

Virtually every modern heater and thermostat will speak OpenTherm, but Remeha in their infinite wisdom created their own protocol called R-Bus. This protocol is to the best of my knowledge completely undocumented, so this is my attempt at doing that.

## Current status

I have collected an oscilloscope capture of the wires between my [Remeha Elga Ace](https://www.remeha.nl/product/elga-ace) heat pump and [Remeha eTwist](https://www.remeha.nl/product/etwist) thermostat. This can be found as a compressed CSV file in `RigolDS1.tar.xz`.

It appears to be a simple on-off keying scheme with a 500kHz carrier and a 10kHz bit rate.

To decode the capture, I first demodulate it with `demodulate.py`, and then import `demodulated_output.csv` in [urh](https://github.com/jopohl/urh). Automated detection worked correctly, but I did set the pause threshold and message length divisor to 10. The analysis tab proved unhelpful so I just exported the data to `protocol.proto.xml`.

My hunch is that it's regular old 8N1 UART data, but possibly inverted. In `decode_bytes.py` I read the exported XML from urh, verify start and stop bits, and extract the data bits. The output is stored in `messages.txt`, a sample is provided below:

```
80 00 00 00 A0 5F 00 80 04 40 80 D3 8F
80 00 80 00 D0 CF 80 7F 04 40 80 17 05 6C 20 A4 5C E9 90
80 00 00 00 A0 5F 00 C0 04 80 08 F1 0C
80 00 80 00 90 AF 40 7F 04 80 08 88 00 90 60 9B E6
```

If you look at the raw capture you can see two slightly different magnitudes, so I think it is reasonable to assume this are the two devices in a request/response interaction. It seems like the first bytes are just some kind of addressing or synchronization, with the third byte being `00` in the request and `80` in the response. Possibly the fifth byte could be some message ID.

## Future ideas

* Build a datalogger. Knowing more or less how the physical layer works it should be doable to log the data for an extended period of time.
* Correlate data with official app interactions and results. Compare data from the [Remeha Home app](https://www.remeha.nl/product/remeha-home-app) with logged data, to identify messages corresponding to temperature values and actions in the app.
* Install their offcial [gateway](https://tools.remeha.nl/wp-content/uploads/sites/11/2020/11/Installatiehandleiding-gateway-16.pdf), and correlate OpenTherm and R-Bus messages. Easier to correlate, but harder to set up and will not capture proprietary functionality.