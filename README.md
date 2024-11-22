# R-Bus

Virtually every modern heater and thermostat will speak OpenTherm, but Remeha in their infinite wisdom created their own protocol called R-Bus. This protocol is to the best of my knowledge completely undocumented, so this is my attempt at doing that.

## Current status

### Nov 8, 2024

I have started building a parser that breaks a stream of bytes from the logger into messages.
Turns out I was decoding the bit order wrong, and now some things are more obvious.
The format seems to be


| byte | meaning |
|---|---|
|`01 00`| header |
| `01` | request/reply |
| `00` | some bit flags? |
| `07` | payload length |
| `F7 01 FE` | unknown |
| `10 03 01 FF FF 85 9C` | payload |

### Nov 6, 2024

I have built a data logger with a comparator and an Arduino, and collected a good long chunk of messages in [log.txt](log.txt),
while simultaneously collecting screenshots of the official app in [screenshots](screenshots) and adjusting the temperature between 20&deg;C and 22&deg;C.

The schematic of the datalogger is in [demodulator.pdf](demodulator.pdf), and the Arduino sketch is in [echo.ino](echo/echo.ino).

Analysis of the new data tbd.

### Oct 14, 2024

I have collected an oscilloscope capture of the wires between my [Remeha Elga Ace](https://www.remeha.nl/product/elga-ace) heat pump and [Remeha eTwist](https://www.remeha.nl/product/etwist) thermostat. This can be found as a compressed CSV file in `RigolDS1.tar.xz`.

It appears to be a simple on-off keying scheme with a 500kHz carrier and a 10kHz bit rate.

To decode the capture, I first demodulate it with `demodulate.py`, and then import `demodulated_output.csv` in [urh](https://github.com/jopohl/urh). Automated detection worked correctly, but I did set the pause threshold and message length divisor to 10. The analysis tab proved unhelpful so I just exported the data to `protocol.proto.xml`.

My hunch is that it's regular old 8N1 UART data, but possibly inverted. In `decode_bytes.py` I read the exported XML from urh, verify start and stop bits, and extract the data bits. The output is stored in `messages.txt`, a sample is provided below:

```
80 00 00 00 A0 5F 00 80 2C C4 80 F9 95
80 00 80 00 D0 CF 80 7F 2C C4 80 00 00 00 00 00 00 1D 6E
80 00 00 00 A0 5F 00 80 2C 44 80 F0 15
80 00 80 00 D0 CF 80 7F 2C 44 80 00 00 00 00 00 00 2E ED
```

If you look at the raw capture you can see two slightly different magnitudes, so I think it is reasonable to assume this are the two devices in a request/response interaction. It seems like the first bytes are just some kind of addressing or synchronization, with the third byte being `00` in the request and `80` in the response. Possibly the fifth byte could be some message ID.

In some of the messages the last 8 bytes look like it could be an uint64 (`00 00 00 00 00 00 2E ED`), hopefully representing some useful value. The request has two bytes in that place. (`F9 95`) The three bytes before that match in the request and reply, and the byte before that is off by one. (`80 2C 44 80` -> `7F 2C 44 80`) Maybe there is some register ID or message sequence number in there?
