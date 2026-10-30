from app.sources import vendor


def test_tidy_vendor_names():
    assert vendor._tidy("Samsung Electronics Co.,Ltd") == "Samsung Electronics"
    assert vendor._tidy("Universal Global Scientific Industrial.") == "Universal Global Scientific Industrial"
    assert vendor._tidy("Intel Corporate") == "Intel"
    assert vendor._tidy("Philips Lighting BV") == "Philips Lighting"
    assert vendor._tidy("Apple, Inc.") == "Apple"
    assert vendor._tidy("Roku, Inc") == "Roku"


def test_parse_and_lookup(tmp_path):
    class C:
        config_path = str(tmp_path)
    (tmp_path / "manuf.txt").write_text(
        "# comment\n"
        "00:17:88         \tPhilipsLight\tPhilips Lighting BV\n"
        "70:B3:D5:00:00:00/36\tSomeIoT\tSome IoT Maker Ltd\n"
        "70:B3:D5         \tIEEERegi\tIEEE Registration Authority\n"
    )
    v = vendor.Vendors(C())
    assert v.lookup("00:17:88:46:be:38") == "Philips Lighting"
    assert v.lookup("70:b3:d5:00:00:01") == "Some IoT Maker"          # longest prefix wins
    assert v.lookup("70:b3:d5:ff:00:01") == "IEEE Registration Authority"
    assert v.lookup("16:01:45:de:91:d0") is None
