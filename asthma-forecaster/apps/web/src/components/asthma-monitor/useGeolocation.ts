"use client"

import * as React from "react"

const STORAGE_KEY = "asthma_risk_location"

export type GeolocationStatus = "loading" | "granted" | "denied" | "unavailable" | "error"

/** Location string for API: "lat,lon" (e.g. "37.77,-122.42"). */
export function useGeolocation() {
  const [location, setLocation] = React.useState<string | null>(null)
  const [status, setStatus] = React.useState<GeolocationStatus>("loading")

  const requestLocation = React.useCallback(() => {
    setStatus("loading")
    setLocation(null)
    if (typeof window === "undefined" || !window.navigator?.geolocation) {
      setStatus("unavailable")
      return
    }
    try {
      window.localStorage.removeItem(STORAGE_KEY)
    } catch {
      // ignore
    }

    window.navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = Math.round(pos.coords.latitude * 10000) / 10000
        const lon = Math.round(pos.coords.longitude * 10000) / 10000
        const value = `${lat},${lon}`
        setLocation(value)
        setStatus("granted")
        try {
          window.localStorage.setItem(STORAGE_KEY, value)
        } catch {
          // ignore
        }
      },
      (err) => {
        if (err.code === 1) setStatus("denied")
        else if (err.code === 2) setStatus("error")
        else setStatus("error")
      },
      { enableHighAccuracy: false, timeout: 15000, maximumAge: 1000 * 60 * 60 }
    )
  }, [])

  React.useEffect(() => {
    if (typeof window === "undefined") {
      setStatus("unavailable")
      return
    }
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY)
      if (stored && /^-?\d+\.?\d*,-?\d+\.?\d*$/.test(stored.trim())) {
        setLocation(stored.trim())
        setStatus("granted")
        return
      }
    } catch {
      // ignore
    }
    requestLocation()
  }, [requestLocation])

  return { location, status, requestLocation }
}
