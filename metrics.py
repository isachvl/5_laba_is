from math import comb,sqrt
def pass_metrics(n,c,k):
    if not 0<=c<=n or not 1<=k<=n:raise ValueError('Invalid n, c or k')
    denominator=comb(n,k)
    return {'pass_all':comb(c,k)/denominator if c>=k else 0.,
            'pass_any':1-(comb(n-c,k)/denominator if n-c>=k else 0.)}
def wilson(c,n):
    if n<=0 or not 0<=c<=n:raise ValueError('Invalid sample')
    z=1.96;p=c/n;scale=1+z*z/n
    center=(p+z*z/(2*n))/scale
    half=z*sqrt(p*(1-p)/n+z*z/(4*n*n))/scale
    return [center-half,center+half]
if __name__=='__main__':
    assert pass_metrics(5,3,1)['pass_all']==.6
    assert pass_metrics(5,3,2)=={'pass_all':.3,'pass_any':.9}
    assert pass_metrics(5,3,3)['pass_all']==.1
    assert pass_metrics(5,4,2)=={'pass_all':.6,'pass_any':1.}
    assert pass_metrics(5,4,5)['pass_all']==0
    low,high=wilson(10,16)
    assert abs(low-.3864)<.002 and abs(high-.8152)<.002
    print('pass^k, pass@k and Wilson checks passed')
