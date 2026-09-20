//! Event model, privacy reduction and trace format of FidusAchates.
//!
//! This crate is the privacy boundary of the project. A raw key code enters
//! [`reduce::Reducer`] and never comes out: what comes out is a
//! [`record::Record`], a type that has no field able to hold one.
//!
//! No I/O and no dependency, so that all of it can be unit-tested and read in
//! one sitting.

#![forbid(unsafe_code)]

pub mod biomech;
pub mod codes;
pub mod keyclass;
pub mod record;
pub mod reduce;
#[cfg(feature = "research-trace")]
pub mod trace;
