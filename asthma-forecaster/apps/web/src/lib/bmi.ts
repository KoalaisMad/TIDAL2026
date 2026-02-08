/** Parse height string to meters. Supports: "5'8"", "5' 8"", "173 cm", "1.73 m" */
export function parseHeightToMeters(height: string): number | null {
  const s = height.trim()
  if (!s) return null
  const cmMatch = s.match(/^(\d+(?:\.\d+)?)\s*cm$/i)
  if (cmMatch) {
    const cm = parseFloat(cmMatch[1])
    return cm > 0 && cm < 300 ? cm / 100 : null
  }
  const mMatch = s.match(/^(\d+(?:\.\d+)?)\s*m$/i)
  if (mMatch) {
    const m = parseFloat(mMatch[1])
    return m > 0 && m < 3 ? m : null
  }
  const ftInMatch = s.match(/^(\d+)\s*['\u2019]?\s*(\d+(?:\.\d+)?)\s*(?:["\u201d]|in\.?)?$/i)
  if (ftInMatch) {
    const ft = parseInt(ftInMatch[1], 10)
    const inch = parseFloat(ftInMatch[2])
    if (ft >= 2 && ft <= 8 && inch >= 0 && inch < 12) {
      return ft * 0.3048 + inch * 0.0254
    }
    return null
  }
  const ftOnly = s.match(/^(\d+)\s*['\u2019]?\s*$/i)
  if (ftOnly) {
    const ft = parseInt(ftOnly[1], 10)
    return ft >= 2 && ft <= 8 ? ft * 0.3048 : null
  }
  return null
}

/** Parse weight string to kg. Supports: "68 kg", "150 lbs" */
export function parseWeightToKg(weight: string): number | null {
  const s = weight.trim()
  if (!s) return null
  const kgMatch = s.match(/^(\d+(?:\.\d+)?)\s*kg$/i)
  if (kgMatch) {
    const kg = parseFloat(kgMatch[1])
    return kg > 0 && kg < 500 ? kg : null
  }
  const lbsMatch = s.match(/^(\d+(?:\.\d+)?)\s*(?:lbs?|lb)?$/i)
  if (lbsMatch) {
    const lbs = parseFloat(lbsMatch[1])
    return lbs > 0 && lbs < 1500 ? lbs / 2.205 : null
  }
  const num = parseFloat(s)
  if (isNaN(num) || num <= 0) return null
  if (num < 150) return num < 300 ? num : null
  return num / 2.205
}

/** Compute BMI from height (m) and weight (kg). Returns null if invalid. */
export function computeBmi(heightM: number | null, weightKg: number | null): number | null {
  if (heightM == null || weightKg == null || heightM <= 0) return null
  const value = weightKg / (heightM * heightM)
  return value > 10 && value < 80 ? Math.round(value * 10) / 10 : null
}

export function bmiCategory(bmi: number): string {
  if (bmi < 18.5) return "Underweight"
  if (bmi < 25) return "Normal"
  if (bmi < 30) return "Overweight"
  return "Obese"
}
