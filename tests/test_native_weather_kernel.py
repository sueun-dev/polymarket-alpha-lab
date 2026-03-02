from core.native_weather_kernel import NativeS02WeatherKernel


def test_native_weather_kernel_python_fallback_temperature():
    k = NativeS02WeatherKernel(binary_path="/definitely/missing/s02_weather_signal_engine")
    prob, conf = k.temperature_probability([85, 86, 84, 88], threshold_f=80.0, above=True)
    assert prob == 1.0
    assert 0.0 <= conf <= 1.0


def test_native_weather_kernel_python_fallback_precipitation():
    k = NativeS02WeatherKernel(binary_path="/definitely/missing/s02_weather_signal_engine")
    prob, conf = k.precipitation_probability([10, 20, 30, 40])
    assert abs(prob - 0.25) < 1e-9
    assert 0.0 <= conf <= 1.0


def test_native_weather_kernel_strict_mode_requires_binary(monkeypatch):
    monkeypatch.setenv("S02_WEATHER_NATIVE_ONLY", "1")
    try:
        NativeS02WeatherKernel(binary_path="/definitely/missing/s02_weather_signal_engine")
        assert False, "expected RuntimeError when native-only mode is enabled"
    except RuntimeError:
        pass
