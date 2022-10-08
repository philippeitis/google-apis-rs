pub mod duration {
    use std::fmt::Formatter;
    use std::str::FromStr;

    use serde::{Deserialize, Deserializer, Serializer};

    use chrono::Duration;

    const MAX_SECONDS: i64 = 315576000000i64;

    #[derive(Debug)]
    enum ParseDurationError {
        MissingSecondSuffix,
        NanosTooSmall,
        ParseIntError(std::num::ParseIntError),
        SecondOverflow { seconds: i64, max_seconds: i64 },
        SecondUnderflow { seconds: i64, min_seconds: i64 },
    }

    impl From<std::num::ParseIntError> for ParseDurationError {
        fn from(pie: std::num::ParseIntError) -> Self {
            ParseDurationError::ParseIntError(pie)
        }
    }

    impl std::fmt::Display for ParseDurationError {
        fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
            match self {
                ParseDurationError::MissingSecondSuffix => write!(f, "'s' suffix was not present"),
                ParseDurationError::NanosTooSmall => {
                    write!(f, "more than 9 digits of second precision required")
                }
                ParseDurationError::ParseIntError(pie) => write!(f, "{:?}", pie),
                ParseDurationError::SecondOverflow {
                    seconds,
                    max_seconds,
                } => write!(
                    f,
                    "seconds overflow (got {}, maximum seconds possible {})",
                    seconds, max_seconds
                ),
                ParseDurationError::SecondUnderflow {
                    seconds,
                    min_seconds,
                } => write!(
                    f,
                    "seconds underflow (got {}, minimum seconds possible {})",
                    seconds, min_seconds
                ),
            }
        }
    }

    impl std::error::Error for ParseDurationError {}

    fn parse_duration(s: &str) -> Result<Duration, ParseDurationError> {
        // TODO: Test strings like -.s, -0.0s
        let value = match s.strip_suffix('s') {
            None => return Err(ParseDurationError::MissingSecondSuffix),
            Some(v) => v,
        };

        let (seconds, nanoseconds) = if let Some((seconds, nanos)) = value.split_once('.') {
            let is_neg = seconds.starts_with("-");
            let seconds = i64::from_str(seconds)?;
            let nano_magnitude = nanos.chars().filter(|c| c.is_digit(10)).count() as u32;
            if nano_magnitude > 9 {
                // not enough precision to model the remaining digits
                return Err(ParseDurationError::NanosTooSmall);
            }

            // u32::from_str prevents negative nanos (eg '0.-12s) -> lossless conversion to i32
            // 10_u32.pow(...) scales number to appropriate # of nanoseconds
            let nanos = u32::from_str(nanos)? as i32;

            let mut nanos = nanos * 10_i32.pow(9 - nano_magnitude);
            if is_neg {
                nanos = -nanos;
            }
            (seconds, nanos)
        } else {
            (i64::from_str(value)?, 0)
        };

        if seconds >= MAX_SECONDS {
            Err(ParseDurationError::SecondOverflow {
                seconds,
                max_seconds: MAX_SECONDS,
            })
        } else if seconds <= -MAX_SECONDS {
            Err(ParseDurationError::SecondUnderflow {
                seconds,
                min_seconds: -MAX_SECONDS,
            })
        } else {
            Ok(Duration::seconds(seconds) + Duration::nanoseconds(nanoseconds.into()))
        }
    }

    pub fn serialize<S>(x: &Option<Duration>, s: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        match x {
            None => s.serialize_none(),
            Some(x) => {
                let seconds = x.num_seconds();
                let nanoseconds = (*x - Duration::seconds(seconds))
                    .num_nanoseconds()
                    .expect("absolute number of nanoseconds is less than 1 billion")
                    as i32;
                if nanoseconds != 0 {
                    if seconds == 0 && nanoseconds.is_negative() {
                        s.serialize_str(&format!("-0.{:0>9}s", nanoseconds.abs()))
                    } else {
                        s.serialize_str(&format!("{}.{:0>9}s", seconds, nanoseconds.abs()))
                    }
                } else {
                    s.serialize_str(&format!("{}s", seconds))
                }
            }
        }
    }

    pub fn deserialize<'de, D>(deserializer: D) -> Result<Option<Duration>, D::Error>
    where
        D: Deserializer<'de>,
    {
        let s: Option<&str> = Deserialize::deserialize(deserializer)?;
        s.map(parse_duration)
            .transpose()
            .map_err(serde::de::Error::custom)
    }
}

pub mod urlsafe_base64 {
    use serde::{Deserialize, Deserializer, Serializer};

    pub fn serialize<S>(x: &Option<Vec<u8>>, s: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        match x {
            None => s.serialize_none(),
            Some(x) => s.serialize_some(&base64::encode_config(x, base64::URL_SAFE)),
        }
    }

    pub fn deserialize<'de, D>(deserializer: D) -> Result<Option<Vec<u8>>, D::Error>
    where
        D: Deserializer<'de>,
    {
        let s: Option<&str> = Deserialize::deserialize(deserializer)?;
        s.map(|s| base64::decode_config(s, base64::URL_SAFE))
            .transpose()
            .map_err(serde::de::Error::custom)
    }
}

pub mod field_mask {
    use crate::FieldMask;
    /// Implementation based on `https://chromium.googlesource.com/infra/luci/luci-go/+/23ea7a05c6a5/common/proto/fieldmasks.go#184`
    use serde::{Deserialize, Deserializer, Serializer};

    fn snakecase(source: &str) -> String {
        let mut dest = String::with_capacity(source.len() + 5);
        for c in source.chars() {
            if c.is_ascii_uppercase() {
                dest.push('_');
                dest.push(c.to_ascii_lowercase());
            } else {
                dest.push(c);
            }
        }
        dest
    }

    fn parse_field_mask(s: &str) -> FieldMask {
        let mut in_quotes = false;
        let mut prev_ind = 0;
        let mut paths = Vec::new();
        for (i, c) in s.chars().enumerate() {
            if c == '`' {
                in_quotes = !in_quotes;
            } else if in_quotes {
                continue;
            } else if c == ',' {
                paths.push(snakecase(&s[prev_ind..i]));
                prev_ind = i + 1;
            }
        }
        paths.push(snakecase(&s[prev_ind..]));
        FieldMask(paths)
    }

    pub fn serialize<S>(x: &Option<FieldMask>, s: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        match x {
            None => s.serialize_none(),
            Some(fieldmask) => s.serialize_some(fieldmask.to_string().as_str()),
        }
    }

    pub fn deserialize<'de, D>(deserializer: D) -> Result<Option<FieldMask>, D::Error>
    where
        D: Deserializer<'de>,
    {
        let s: Option<&str> = Deserialize::deserialize(deserializer)?;
        Ok(s.map(parse_field_mask))
    }
}

pub mod str_like {
    /// Implementation based on `https://chromium.googlesource.com/infra/luci/luci-go/+/23ea7a05c6a5/common/proto/fieldmasks.go#184`
    use serde::{Deserialize, Deserializer, Serializer};
    use std::str::FromStr;

    pub fn serialize<S, T>(x: &Option<T>, s: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
        T: std::fmt::Display,
    {
        match x {
            None => s.serialize_none(),
            Some(num) => s.serialize_some(num.to_string().as_str()),
        }
    }

    pub fn deserialize<'de, D, T>(deserializer: D) -> Result<Option<T>, D::Error>
    where
        D: Deserializer<'de>,
        T: FromStr,
        <T as FromStr>::Err: std::fmt::Display,
    {
        let s: Option<&str> = Deserialize::deserialize(deserializer)?;
        s.map(T::from_str)
            .transpose()
            .map_err(serde::de::Error::custom)
    }
}

#[cfg(test)]
mod test {
    use super::{duration, field_mask, str_like, urlsafe_base64};
    use crate::FieldMask;
    use serde::{Deserialize, Serialize};

    #[derive(Serialize, Deserialize, Debug, PartialEq)]
    struct DurationWrapper {
        #[serde(with = "duration")]
        duration: Option<chrono::Duration>,
    }

    #[derive(Serialize, Deserialize, Debug, PartialEq)]
    struct Base64Wrapper {
        #[serde(with = "urlsafe_base64")]
        bytes: Option<Vec<u8>>,
    }

    #[derive(Serialize, Deserialize, Debug, PartialEq)]
    struct FieldMaskWrapper {
        #[serde(with = "field_mask")]
        fields: Option<FieldMask>,
    }

    #[derive(Serialize, Deserialize, Debug, PartialEq)]
    struct I64Wrapper {
        #[serde(with = "str_like")]
        num: Option<i64>,
    }

    #[test]
    fn test_duration_de_success_cases() {
        let durations = [
            ("-0.2s", -200_000_000),
            ("0.000000001s", 1),
            ("999.999999999s", 999_999_999_999),
            ("129s", 129_000_000_000),
            ("0.123456789s", 123_456_789),
        ];
        for (repr, nanos) in durations.into_iter() {
            let wrapper: DurationWrapper =
                serde_json::from_str(&format!("{{\"duration\": \"{}\"}}", repr)).unwrap();
            assert_eq!(
                Some(nanos),
                wrapper.duration.unwrap().num_nanoseconds(),
                "parsed \"{}\" expecting Duration with {}ns",
                repr,
                nanos
            );
        }
    }

    #[test]
    fn test_duration_de_failure_cases() {
        let durations = ["1.-3s", "1.1111111111s", "1.2"];
        for repr in durations.into_iter() {
            assert!(
                serde_json::from_str::<DurationWrapper>(&format!("{{\"duration\": \"{}\"}}", repr))
                    .is_err(),
                "parsed \"{}\" expecting err",
                repr
            );
        }
    }

    #[test]
    fn test_duration_ser_success_cases() {
        let durations = [
            -200_000_000,
            1,
            999_999_999_999,
            129_000_000_000,
            123_456_789,
        ];

        for nanos in durations.into_iter() {
            let wrapper = DurationWrapper {
                duration: Some(chrono::Duration::nanoseconds(nanos)),
            };
            let s = serde_json::to_string(&wrapper);
            assert!(s.is_ok(), "Could not serialize {}ns", nanos);
            let s = s.unwrap();
            assert_eq!(
                wrapper,
                serde_json::from_str(&s).unwrap(),
                "round trip should return same duration"
            );
        }
    }

    #[test]
    fn urlsafe_base64_de_success_cases() {
        let wrapper: Base64Wrapper =
            serde_json::from_str(r#"{"bytes": "aGVsbG8gd29ybGQ="}"#).unwrap();
        assert_eq!(
            Some(b"hello world".as_slice()),
            wrapper.bytes.as_ref().map(Vec::as_slice)
        );
    }

    #[test]
    fn urlsafe_base64_de_failure_cases() {
        assert!(serde_json::from_str::<Base64Wrapper>(r#"{"bytes": "aGVsbG8gd29ybG+Q"}"#).is_err());
    }

    #[test]
    fn urlsafe_base64_roundtrip() {
        let wrapper = Base64Wrapper {
            bytes: Some(b"Hello world!".to_vec()),
        };
        let s = serde_json::to_string(&wrapper).expect("serialization of bytes infallible");
        assert_eq!(wrapper, serde_json::from_str::<Base64Wrapper>(&s).unwrap());
    }

    #[test]
    fn field_mask_roundtrip() {
        let wrapper = FieldMaskWrapper {
            fields: Some(FieldMask(vec![
                "user.display_name".to_string(),
                "photo".to_string(),
            ])),
        };
        let json_repr = &serde_json::to_string(&wrapper);
        assert!(json_repr.is_ok(), "serialization should succeed");
        assert_eq!(
            wrapper,
            serde_json::from_str(r#"{"fields": "user.displayName,photo"}"#).unwrap()
        );
        assert_eq!(
            wrapper,
            serde_json::from_str(json_repr.as_ref().unwrap()).unwrap(),
            "round trip should succeed"
        );
    }

    #[test]
    fn num_roundtrip() {
        let wrapper = I64Wrapper {
            num: Some(i64::MAX),
        };

        let json_repr = &serde_json::to_string(&wrapper);
        assert!(json_repr.is_ok(), "serialization should succeed");
        assert_eq!(
            wrapper,
            serde_json::from_str(&format!("{{\"num\": \"{}\"}}", i64::MAX)).unwrap()
        );
        assert_eq!(
            wrapper,
            serde_json::from_str(json_repr.as_ref().unwrap()).unwrap(),
            "round trip should succeed"
        );
    }
}
