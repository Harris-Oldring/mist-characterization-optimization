import matplotlib.pyplot as plt

# def analysis(data,func_name):
#     params,_ =al.lib[func_name]['fit_func'](data)
#     x = np.linspace(np.min(data), np.max(data), 1000)
#     y = al.lib[func_name]['pdf_func'](x, params)
#     plt.plot(x,y)
#     plt.show()


# def plot_general_page(self, metrics, title, scope, channel, source=None, figure=None):
#     if not self.pdf_pages:
#         return

#     if figure is not None:
#         fig = figure
#     else:
#         fig, ax = plt.subplots(figsize=(10, 6))
#         ax.axis('off')
#         heading = f"General Analysis - {source if source else 'General'}"
#         subtitle = f"Scope: {scope}, Channel: {channel if channel is not None else 'all'}"
#         summary_lines = [heading, subtitle, '']
#         summary_lines += [f"{key}: {value}" for key, value in metrics.items()]
#         fig.text(0.01, 0.99, "\n".join(summary_lines), fontsize=10, va='top', family='monospace')
#         fig.tight_layout()

#     self.pdf_pages.savefig(fig)
#     plt.close(fig)

def plot_hist_with_fit(self, results, usrconfig, summary_text=None):
    '''
    Plots a histogram with a fitted probability density function.
    '''
    data=results.data
    xfit=results.xfit
    yfit=results.yfit
    fit_dict=results.fit_dict
    nbins=results.nbins #round(np.sqrt(len(data)))
    threshold=results.threshold
    # Load in plotting parameters from analysis and construct figure
    xlabel, fit_type, units, threshold = fit_dict['xlabel'], fit_dict['fit_type'], fit_dict['units'], fit_dict['threshold']
    xlabel += f" ({units})" if units else ""
    scope = f"Channel {channel}" if channel != 'all' else "Aggregate"
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 9))
    ylabel=fit_dict['ylabel'] if fit_dict['xlabel'] else "Frequency"

    ## PDF Fit plot
    ax1.set_title(f"{fit_dict['title']} ({scope})")
    ax1.set_xlabel(xlabel)
    ax1.set_ylabel(ylabel)
    ax1.hist(data, bins=nbins, density=True,histtype="step")
    ax1.plot(xfit, yfit, label=f'{fit_type} PDF Fit')
    ax1.legend()

    ## CDF Fit plot
    y_cdf = pdf2cdf(xfit, yfit)
    ax2.set_title(f"{fit_dict['title']} ({scope})")
    ax2.set_xlabel(xlabel)
    ax2.set_ylabel(ylabel)
    ax2.set_ylim(1e-4,1.1)
    ax2.hist(data, bins=nbins, density=True, cumulative=True, histtype="step")
    ax2.plot(xfit, y_cdf, label=f'{fit_type} CDF Fit')
    ### Plot threshold, if Applicable
    if threshold:
    #  thresh = get_thresh(xfit, y_cdf,rate=threshold) #should be done along with analysis
    #  cdf_at_thresh = make_interp_spline(xfit, y_cdf, 5)(thresh)
        ax2.plot(thresh, cdf_at_thresh, label=f"{threshold*100:.2f}% Threshold", marker="x", linestyle="")
        ax2.annotate(f"Threshold = {thresh:.3f} {units}", xy=(thresh, cdf_at_thresh), xytext=(thresh+15, cdf_at_thresh*0.4), textcoords='data')
    ax2.set_yscale('log')
    ax2.legend()

    ## Add summary text detailing important parameters, etc.
    if summary_text:
        fig.tight_layout(rect=[0, 0.12, 1, 0.95])
        fig.text(0.01, 0.02, summary_text, fontsize=8, va='bottom', ha='left')
    else:
        fig.tight_layout()

    ## Save or show plot
    if self.pdf_pages and self.save:
        self.logger.info(f"Saving plot for {fit_dict['name']} ({scope}) to PDF")
        self.pdf_pages.savefig(fig)
        plt.close(fig)
    elif self.pdf_pages:
        self.logger.info(f"Displaying plot for {fit_dict['name']} ({scope})")
        plt.show()

    
